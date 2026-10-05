import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete
from sqlalchemy.orm import Session

from api.dependencies import (
    get_session,
    get_telemetry_repo,
    get_health_snapshot_repo,
)
from api.exceptions import MissionNotFoundError, InvalidTimeRangeError
from api.schemas import (
    MissionListResponse,
    MissionSummary,
    MissionResponse,
    TelemetryResponse,
    ReplayResponse,
    ReplayPoint,
    HealthResponse,
    PredictionResponse,
    MissionReportResponse,
    BaselineResponse,
)
from telemetry.models import IngestionEvent, Telemetry
from telemetry.repository import TelemetryRepository
from twin import baseline
from twin.report import build_report
from twin.service import (
    CHT_ROUGHNESS_LIMIT,
    ROUGHNESS_WINDOW,
    RPM_ROUGHNESS_LIMIT,
    VIBRATION_RMS_LIMIT,
)
from twin.models import HealthSnapshot
from twin.repository import HealthSnapshotRepository


router = APIRouter()


@router.get(
    "/missions",
    response_model=MissionListResponse,
)
def list_missions(
    session: Session = Depends(get_session),
    telemetry_repo: TelemetryRepository = Depends(get_telemetry_repo),
):
    mission_ids = telemetry_repo.get_distinct_missions(session)

    return MissionListResponse(
        missions=[
            MissionSummary(mission_id=mid)
            for mid in mission_ids
        ]
    )


SIMULATION_CONTROLLER_URL = "http://host.docker.internal:9000"


def _running_mission() -> str | None:
    """Mission the simulator is running now, or None. Unreachable counts as
    not running: the controller is down, so nothing is being simulated."""

    try:
        status = requests.get(f"{SIMULATION_CONTROLLER_URL}/simulation/status", timeout=3).json()
    except (requests.RequestException, ValueError):
        return None
    return status.get("mission_id") if status.get("status") == "running" else None


def _delete_missions(session: Session, mission_ids: list[str]) -> int:
    for model in (HealthSnapshot, IngestionEvent, Telemetry):
        session.execute(delete(model).where(model.mission_id.in_(mission_ids)))
    session.commit()
    return len(mission_ids)


@router.delete("/missions")
def delete_all_missions(
    session: Session = Depends(get_session),
    telemetry_repo: TelemetryRepository = Depends(get_telemetry_repo),
):
    """Permanently delete every mission (a fresh start)."""

    running = _running_mission()
    if running:
        raise HTTPException(
            status_code=409,
            detail=f"Mission {running} is running. Stop the simulation before deleting data.",
        )
    return {"deleted_missions": _delete_missions(session, telemetry_repo.get_distinct_missions(session))}


@router.delete("/missions/{mission_id}")
def delete_mission(
    mission_id: str,
    session: Session = Depends(get_session),
    telemetry_repo: TelemetryRepository = Depends(get_telemetry_repo),
):
    """Permanently delete one mission's telemetry, health snapshots and
    ingestion events."""

    if mission_id not in telemetry_repo.get_distinct_missions(session):
        raise MissionNotFoundError(mission_id)
    if _running_mission() == mission_id:
        raise HTTPException(
            status_code=409,
            detail=f"Mission {mission_id} is running. Stop the simulation before deleting it.",
        )
    return {"deleted_missions": _delete_missions(session, [mission_id])}


@router.get(
    "/missions/{mission_id}",
    response_model=MissionResponse,
)
def get_mission(
    mission_id: str,
    session: Session = Depends(get_session),
    telemetry_repo: TelemetryRepository = Depends(get_telemetry_repo),
):
    rows = telemetry_repo.get_by_mission(
        session,
        mission_id,
    )

    if not rows:
        raise MissionNotFoundError(mission_id)

    return MissionResponse(
        mission_id=mission_id,
        engine_id=rows[0].engine_id,
        start_time=rows[0].time,
        end_time=rows[-1].time,
        sample_count=len(rows),
    )


@router.get(
    "/missions/{mission_id}/report",
    response_model=MissionReportResponse,
)
def mission_report(
    mission_id: str,
    session: Session = Depends(get_session),
    telemetry_repo: TelemetryRepository = Depends(get_telemetry_repo),
    health_repo: HealthSnapshotRepository = Depends(get_health_snapshot_repo),
):
    rows = telemetry_repo.get_by_mission(session, mission_id)

    if not rows:
        raise MissionNotFoundError(mission_id)

    snapshots = health_repo.get_by_mission(
        session,
        rows[0].engine_id,
        mission_id,
    )

    return MissionReportResponse(**build_report(mission_id, rows, snapshots))


@router.get(
    "/missions/{mission_id}/telemetry",
    response_model=list[TelemetryResponse],
)
def mission_telemetry(
    mission_id: str,
    start: str | None = Query(default=None),
    end: str | None = Query(default=None),
    session: Session = Depends(get_session),
    telemetry_repo: TelemetryRepository = Depends(get_telemetry_repo),
):
    if start and end:
        if start >= end:
            raise InvalidTimeRangeError(
                "start must be before end"
            )

        rows = telemetry_repo.get_by_time_range(
            session,
            engine_id=_engine_id_for_mission(
                session,
                telemetry_repo,
                mission_id,
            ),
            mission_id=mission_id,
            start_time=start,
            end_time=end,
        )

    else:
        rows = telemetry_repo.get_by_mission(
            session,
            mission_id,
        )

    if not rows:
        raise MissionNotFoundError(mission_id)

    return [
        TelemetryResponse.from_row(r)
        for r in rows
    ]


@router.get(
    "/missions/{mission_id}/replay",
    response_model=ReplayResponse,
)
def mission_replay(
    mission_id: str,
    session: Session = Depends(get_session),
    telemetry_repo: TelemetryRepository = Depends(get_telemetry_repo),
    health_repo: HealthSnapshotRepository = Depends(
        get_health_snapshot_repo
    ),
):
    rows = telemetry_repo.get_by_mission(
        session,
        mission_id,
    )

    if not rows:
        raise MissionNotFoundError(mission_id)

    engine_id = rows[0].engine_id

    snapshots = health_repo.get_by_mission(
        session,
        engine_id,
        mission_id,
    )

    health_by_time = {
        snapshot.time: snapshot
        for snapshot in snapshots
    }

    points = []

    for row in rows:
        snapshot = health_by_time.get(row.time)

        health = None
        prediction = None

        if snapshot is not None:
            health = HealthResponse.from_snapshot(snapshot)

            # Older health snapshots may not contain ML prediction data.
            if (
                snapshot.anomaly_score is not None
                and snapshot.is_anomaly is not None
                and snapshot.confidence is not None
            ):
                prediction = PredictionResponse.from_snapshot(snapshot)

        points.append(
            ReplayPoint(
                timestamp=row.time,
                telemetry=TelemetryResponse.from_row(row),
                health=health,
                prediction=prediction,
            )
        )

    return ReplayResponse(
        mission_id=mission_id,
        engine_id=engine_id,
        points=points,
    )


@router.get(
    "/missions/{mission_id}/baseline",
    response_model=BaselineResponse,
)
def mission_baseline(
    mission_id: str,
    session: Session = Depends(get_session),
    telemetry_repo: TelemetryRepository = Depends(get_telemetry_repo),
):
    rows = telemetry_repo.get_by_mission(
        session,
        mission_id,
    )

    if not rows:
        raise MissionNotFoundError(mission_id)

    # A mission starts with the engine, as in the live twin while the
    # mission is shorter than baseline.HISTORY_SAMPLES.
    expected = baseline.expected_series(
        [
            {
                "throttle": r.throttle,
                "engine_load": r.engine_load,
                "altitude": r.altitude,
                "ambient_temperature": r.ambient_temperature,
            }
            for r in rows
        ],
        from_engine_start=True,
    ) or []

    return BaselineResponse(
        mission_id=mission_id,
        signals=list(baseline.TARGETS) if expected else [],
        expected=[
            {name: round(value, 3) for name, value in row.items()}
            for row in expected
        ],
        roughness_window=ROUGHNESS_WINDOW,
        vibration_rms_limit=VIBRATION_RMS_LIMIT,
        rpm_roughness_limit=RPM_ROUGHNESS_LIMIT,
        cht_roughness_limit=CHT_ROUGHNESS_LIMIT,
    )


def _engine_id_for_mission(
    session: Session,
    telemetry_repo: TelemetryRepository,
    mission_id: str,
) -> str:
    rows = telemetry_repo.get_by_mission(
        session,
        mission_id,
    )

    if not rows:
        raise MissionNotFoundError(mission_id)

    return rows[0].engine_id