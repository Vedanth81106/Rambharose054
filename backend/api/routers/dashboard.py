from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.dependencies import (
    get_session,
    get_telemetry_repo,
    get_health_snapshot_repo,
    get_twin_service,
)
from api.exceptions import EngineNotFoundError
from api.schemas import (
    DashboardResponse,
    TelemetryResponse,
    HealthResponse,
    PredictionResponse,
    AlertResponse,
    HealthHistoryPoint,
)
from telemetry.repository import TelemetryRepository
from twin.repository import HealthSnapshotRepository
from twin.service import DigitalTwinService
from twin.schemas import MLPrediction

router = APIRouter()


@router.get(
    "/dashboard/{engine_id}",
    response_model=DashboardResponse,
)
def dashboard(
    engine_id: str,
    mission_id: str,
    session: Session = Depends(get_session),
    telemetry_repo: TelemetryRepository = Depends(get_telemetry_repo),
    health_repo: HealthSnapshotRepository = Depends(get_health_snapshot_repo),
    twin_service: DigitalTwinService = Depends(get_twin_service),
):
    latest_row = telemetry_repo.get_latest(session, engine_id, mission_id)
    if latest_row is None:
        raise EngineNotFoundError(engine_id)

    latest_telemetry = TelemetryResponse(
        timestamp=latest_row.time,
        engine_id=latest_row.engine_id,
        mission_id=latest_row.mission_id,
        rpm=latest_row.rpm,
        cht=latest_row.cht,
        egt=latest_row.egt,
        oil_pressure=latest_row.oil_pressure,
        oil_temperature=latest_row.oil_temperature,
        fuel_flow=latest_row.fuel_flow,
        vibration=latest_row.vibration,
        battery_voltage=latest_row.battery_voltage,
        alternator_current=latest_row.alternator_current,
        injection_timing=latest_row.injection_timing,
    )

    snapshots = health_repo.get_by_engine(session, engine_id)
    snapshots = [s for s in snapshots if s.mission_id == mission_id]

    health = None
    operating_state = None
    recent_health_history = []

    if snapshots:
        latest_snapshot = snapshots[-1]
        health = HealthResponse(
            overall=latest_snapshot.overall,
            thermal=latest_snapshot.thermal,
            combustion=latest_snapshot.combustion,
            lubrication=latest_snapshot.lubrication,
            mechanical=latest_snapshot.mechanical,
            electrical=latest_snapshot.electrical,
        )
        recent_health_history = [
            HealthHistoryPoint(
                timestamp=s.time,
                health=HealthResponse(
                    overall=s.overall,
                    thermal=s.thermal,
                    combustion=s.combustion,
                    lubrication=s.lubrication,
                    mechanical=s.mechanical,
                    electrical=s.electrical,
                ),
            )
            for s in snapshots[-20:]
        ]

    window = telemetry_repo.get_latest_window(session, engine_id, mission_id)
    if len(window) < 60:
        ml_prediction = MLPrediction(
            anomaly_score=0.0, fault=None, confidence=0.0, rul_hours=None
        )
    else:
        telemetry_window = [
            {
                "rpm": t.rpm,
                "cht": t.cht,
                "egt": t.egt,
                "oil_pressure": t.oil_pressure,
                "oil_temperature": t.oil_temperature,
                "fuel_flow": t.fuel_flow,
                "vibration": t.vibration,
                "battery_voltage": t.battery_voltage,
                "alternator_current": t.alternator_current,
                "injection_timing": t.injection_timing,
            }
            for t in window
        ]
        ml_prediction = twin_service.predictor.predict(telemetry_window)

    prediction = PredictionResponse(
        anomaly_score=ml_prediction.anomaly_score,
        fault=ml_prediction.fault,
        confidence=ml_prediction.confidence,
        rul_hours=ml_prediction.rul_hours,
    )

    if health is not None:
        operating_state = twin_service._determine_operating_state(
            health.overall,
            ml_prediction,
        )

    alerts: list[AlertResponse] = []
    for s in snapshots:
        if s.overall < 60:
            alerts.append(
                AlertResponse(
                    engine_id=engine_id,
                    mission_id=mission_id,
                    severity="DEGRADED",
                    message=f"Overall health dropped to {s.overall}",
                    source="operating_state",
                    timestamp=s.time,
                )
            )

    events = telemetry_repo.get_ingestion_events(session, engine_id, mission_id)
    for e in events:
        alerts.append(
            AlertResponse(
                engine_id=engine_id,
                mission_id=mission_id,
                severity="WARNING",
                message=f"Ingestion event: {e.event_type}",
                source="ingestion_event",
                timestamp=e.event_time,
            )
        )
    alerts.sort(key=lambda a: a.timestamp)

    return DashboardResponse(
        engine_id=engine_id,
        mission_id=mission_id,
        latest_telemetry=latest_telemetry,
        health=health,
        prediction=prediction,
        operating_state=operating_state,
        alerts=alerts,
        recent_health_history=recent_health_history,
    )