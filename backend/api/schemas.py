from datetime import datetime

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------

class TelemetryResponse(BaseModel):
    timestamp: datetime
    engine_id: str
    mission_id: str
    rpm: float
    cht: float
    egt: float
    oil_pressure: float
    oil_temperature: float
    fuel_flow: float
    vibration: float
    battery_voltage: float
    alternator_current: float
    injection_timing: float


# ---------------------------------------------------------------------------
# Health / Prediction (mirror twin/schemas.py shapes, kept separate on purpose
# so the API layer's response contract doesn't break if twin/schemas.py changes)
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    overall: float
    thermal: float
    combustion: float
    lubrication: float
    mechanical: float
    electrical: float


class PredictionResponse(BaseModel):
    anomaly_score: float
    fault: str | None
    confidence: float
    rul_hours: float | None


class EngineHealthResponse(BaseModel):
    engine_id: str
    mission_id: str
    operating_state: str
    health: HealthResponse
    prediction: PredictionResponse


class HealthHistoryPoint(BaseModel):
    timestamp: datetime
    health: HealthResponse


class HealthHistoryResponse(BaseModel):
    engine_id: str
    mission_id: str
    history: list[HealthHistoryPoint]


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

class AlertResponse(BaseModel):
    engine_id: str
    mission_id: str
    severity: str          # NOMINAL / WARNING / DEGRADED / CRITICAL
    message: str
    source: str             # "operating_state" | "ingestion_event"
    timestamp: datetime


# ---------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------

class EngineSummary(BaseModel):
    engine_id: str


class EngineListResponse(BaseModel):
    engines: list[EngineSummary]


# ---------------------------------------------------------------------------
# Missions
# ---------------------------------------------------------------------------

class MissionSummary(BaseModel):
    mission_id: str


class MissionListResponse(BaseModel):
    missions: list[MissionSummary]


class MissionResponse(BaseModel):
    mission_id: str
    engine_id: str
    start_time: datetime
    end_time: datetime
    sample_count: int


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------

class ReplayPoint(BaseModel):
    timestamp: datetime
    telemetry: TelemetryResponse
    health: HealthResponse | None = None


class ReplayResponse(BaseModel):
    mission_id: str
    engine_id: str
    points: list[ReplayPoint]


# ---------------------------------------------------------------------------
# Dashboard (aggregation)
# ---------------------------------------------------------------------------

class DashboardResponse(BaseModel):
    engine_id: str
    mission_id: str
    latest_telemetry: TelemetryResponse | None
    health: HealthResponse | None
    prediction: PredictionResponse | None
    operating_state: str | None
    alerts: list[AlertResponse]
    recent_health_history: list[HealthHistoryPoint]