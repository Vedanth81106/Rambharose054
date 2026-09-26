from twin.schemas import MLPrediction
import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.dependencies import (
    get_session,
    get_telemetry_repo,
    get_health_snapshot_repo,
    get_twin_service,
)
from api.exceptions import EngineNotFoundError
from api.schemas import (
    EngineListResponse,
    EngineSummary,
    TelemetryResponse,
    EngineHealthResponse,
    HealthResponse,
    PredictionResponse,
    HealthHistoryResponse,
    HealthHistoryPoint,
    AlertResponse,
)
from telemetry.repository import TelemetryRepository
from twin.repository import HealthSnapshotRepository
from twin.service import DigitalTwinService

import paho.mqtt.client as mqtt


router = APIRouter()


# ---------------------------------------------------------
# Existing endpoints
# ---------------------------------------------------------

@router.get("/engines", response_model=EngineListResponse)
def list_engines(
    session: Session = Depends(get_session),
    telemetry_repo: TelemetryRepository = Depends(get_telemetry_repo),
):
    engine_ids = telemetry_repo.get_distinct_engines(session)

    return EngineListResponse(
        engines=[
            EngineSummary(engine_id=eid)
            for eid in engine_ids
        ]
    )

@router.get("/engines/{engine_id}/simulation/status")
def get_simulation_status(
    engine_id: str,
    session: Session = Depends(get_session),
    telemetry_repo: TelemetryRepository = Depends(get_telemetry_repo),
):

    try:
        response = requests.get(
            f"{SIMULATION_CONTROLLER_URL}/simulation/status",
            timeout=5,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to get simulation status: {exc}",
        )
        
@router.get(
    "/engines/{engine_id}",
    response_model=EngineSummary,
)
def get_engine(
    engine_id: str,
    session: Session = Depends(get_session),
    telemetry_repo: TelemetryRepository = Depends(get_telemetry_repo),
):

    return EngineSummary(engine_id=engine_id)


# ---------------------------------------------------------
# Fault injection
# ---------------------------------------------------------

@router.post("/engines/{engine_id}/fault")
def inject_fault(
    engine_id: str,
    fault_id: int,
    session: Session = Depends(get_session),
    telemetry_repo: TelemetryRepository = Depends(
        get_telemetry_repo
    ),
):
    if fault_id not in {0, 1, 2, 3, 4}:
        raise HTTPException(
            status_code=400,
            detail="fault_id must be 0, 1, 2, 3, or 4",
        )

    if engine_id not in telemetry_repo.get_distinct_engines(
        session
    ):
        raise EngineNotFoundError(engine_id)

    topic = f"engine/{engine_id}/fault"

    client = mqtt.Client()

    try:
        client.connect(
            "mosquitto",
            1883,
            60,
        )

        client.loop_start()

        message = client.publish(
            topic,
            str(fault_id),
            qos=1,
        )

        message.wait_for_publish()

        client.loop_stop()
        client.disconnect()

    except Exception as exc:
        client.loop_stop()
        client.disconnect()

        raise HTTPException(
            status_code=503,
            detail=f"Failed to publish fault command: {exc}",
        )

    return {
        "engine_id": engine_id,
        "fault_id": fault_id,
        "status": "published",
    }

SIMULATION_CONTROLLER_URL = "http://host.docker.internal:9000"


@router.post("/engines/{engine_id}/simulation/start")
def start_simulation(
    engine_id: str,
    session: Session = Depends(get_session),
    telemetry_repo: TelemetryRepository = Depends(
        get_telemetry_repo
    ),
):

    try:
        response = requests.post(
            f"{SIMULATION_CONTROLLER_URL}/simulation/start",
            timeout=5,
        )

        response.raise_for_status()

        return response.json()

    except requests.RequestException as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to start simulation: {exc}",
        )


@router.post("/engines/{engine_id}/simulation/stop")
def stop_simulation(
    engine_id: str,
    session: Session = Depends(get_session),
    telemetry_repo: TelemetryRepository = Depends(
        get_telemetry_repo
    ),
):

    try:
        response = requests.post(
            f"{SIMULATION_CONTROLLER_URL}/simulation/stop",
            timeout=5,
        )

        response.raise_for_status()

        return response.json()

    except requests.RequestException as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to stop simulation: {exc}",
        )

# ---------------------------------------------------------
# Latest telemetry
# ---------------------------------------------------------

@router.get(
    "/engines/{engine_id}/telemetry/latest",
    response_model=TelemetryResponse,
)
def latest_telemetry(
    engine_id: str,
    mission_id: str,
    session: Session = Depends(get_session),
    telemetry_repo: TelemetryRepository = Depends(
        get_telemetry_repo
    ),
):
    row = telemetry_repo.get_latest(
        session,
        engine_id,
        mission_id,
    )

    if row is None:
        raise EngineNotFoundError(engine_id)

    return TelemetryResponse(
        timestamp=row.time,
        engine_id=row.engine_id,
        mission_id=row.mission_id,
        rpm=row.rpm,
        torque=row.torque,
        cht=row.cht,
        egt=row.egt,
        oil_pressure=row.oil_pressure,
        oil_temperature=row.oil_temperature,
        fuel_flow=row.fuel_flow,
        vibration=row.vibration,
    )


# ---------------------------------------------------------
# Engine health
# ---------------------------------------------------------

@router.get(
    "/engines/{engine_id}/health",
    response_model=EngineHealthResponse,
)
def engine_health(
    engine_id: str,
    mission_id: str,
    session: Session = Depends(get_session),
    telemetry_repo: TelemetryRepository = Depends(
        get_telemetry_repo
    ),
    health_repo: HealthSnapshotRepository = Depends(
        get_health_snapshot_repo
    ),
    twin_service: DigitalTwinService = Depends(
        get_twin_service
    ),
):
    snapshots = health_repo.get_by_engine(
        session,
        engine_id,
    )

    snapshots = [
        s for s in snapshots
        if s.mission_id == mission_id
    ]

    if not snapshots:
        raise EngineNotFoundError(engine_id)

    latest_snapshot = snapshots[-1]

    health = HealthResponse(
        overall=latest_snapshot.overall,
        thermal=latest_snapshot.thermal,
        combustion=latest_snapshot.combustion,
        lubrication=latest_snapshot.lubrication,
        mechanical=latest_snapshot.mechanical,
    )

    window = telemetry_repo.get_latest_window(
        session,
        engine_id,
        mission_id,
    )

    if len(window) < 60:

        ml_prediction = MLPrediction(
            anomaly_score=0.0,
            fault=None,
            confidence=0.0,
            rul_hours=None,
        )

    else:

        telemetry_window = [
            {
                "rpm": t.rpm,
                "cht": t.cht,
                "egt": t.egt,
                "oil_pressure": t.oil_pressure,
                "torque": t.torque,
                "oil_temperature": t.oil_temperature,
                "fuel_flow": t.fuel_flow,
                "vibration": t.vibration,
                "throttle": t.throttle,
                "engine_load": t.engine_load,
                "altitude": t.altitude,
                "ambient_temperature": t.ambient_temperature,
            }
            for t in window
        ]

        ml_prediction = (
            twin_service.predictor.predict(
                telemetry_window
            )
        )

    prediction = PredictionResponse(
        anomaly_score=ml_prediction.anomaly_score,
        fault=ml_prediction.fault,
        confidence=ml_prediction.confidence,
        rul_hours=ml_prediction.rul_hours,
    )

    operating_state = (
        twin_service._determine_operating_state(
            health.overall,
            ml_prediction,
        )
    )

    return EngineHealthResponse(
        engine_id=engine_id,
        mission_id=mission_id,
        operating_state=operating_state,
        health=health,
        prediction=prediction,
    )


# ---------------------------------------------------------
# Health history
# ---------------------------------------------------------

@router.get(
    "/engines/{engine_id}/health/history",
    response_model=HealthHistoryResponse,
)
def health_history(
    engine_id: str,
    mission_id: str,
    session: Session = Depends(get_session),
    health_repo: HealthSnapshotRepository = Depends(
        get_health_snapshot_repo
    ),
):
    snapshots = health_repo.get_by_engine(
        session,
        engine_id,
    )

    snapshots = [
        s for s in snapshots
        if s.mission_id == mission_id
    ]

    if not snapshots:
        raise EngineNotFoundError(engine_id)

    return HealthHistoryResponse(
        engine_id=engine_id,
        mission_id=mission_id,
        history=[
            HealthHistoryPoint(
                timestamp=s.time,
                health=HealthResponse(
                    overall=s.overall,
                    thermal=s.thermal,
                    combustion=s.combustion,
                    lubrication=s.lubrication,
                    mechanical=s.mechanical,
                ),
            )
            for s in snapshots
        ],
    )


# ---------------------------------------------------------
# Alerts
# ---------------------------------------------------------

@router.get(
    "/engines/{engine_id}/alerts",
    response_model=list[AlertResponse],
)
def engine_alerts(
    engine_id: str,
    mission_id: str,
    session: Session = Depends(get_session),
    telemetry_repo: TelemetryRepository = Depends(
        get_telemetry_repo
    ),
    health_repo: HealthSnapshotRepository = Depends(
        get_health_snapshot_repo
    ),
):
    alerts: list[AlertResponse] = []

    snapshots = health_repo.get_by_engine(
        session,
        engine_id,
    )

    snapshots = [
        s for s in snapshots
        if s.mission_id == mission_id
    ]

    for s in snapshots:

        if s.overall < 60:

            alerts.append(
                AlertResponse(
                    engine_id=engine_id,
                    mission_id=mission_id,
                    severity="DEGRADED",
                    message=(
                        f"Overall health dropped to "
                        f"{s.overall}"
                    ),
                    source="operating_state",
                    timestamp=s.time,
                )
            )

    events = telemetry_repo.get_ingestion_events(
        session,
        engine_id,
        mission_id,
    )

    for e in events:

        alerts.append(
            AlertResponse(
                engine_id=engine_id,
                mission_id=mission_id,
                severity="WARNING",
                message=(
                    f"Ingestion event: "
                    f"{e.event_type}"
                ),
                source="ingestion_event",
                timestamp=e.event_time,
            )
        )

    alerts.sort(
        key=lambda a: a.timestamp
    )

    return alerts