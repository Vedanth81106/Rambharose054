from datetime import datetime

from pydantic import BaseModel


class MLPrediction(BaseModel):
    anomaly_score: float
    fault: str | None
    confidence: float
    rul_hours: float | None


class HealthState(BaseModel):
    overall: float
    thermal: float
    combustion: float
    lubrication: float
    mechanical: float
    electrical: float


class DigitalTwinState(BaseModel):
    engine_id: str
    mission_id: str
    operating_state: str

    health: HealthState
    prediction: MLPrediction


class HealthSnapshot(BaseModel):
    engine_id: str
    mission_id: str
    timestamp: datetime
    health: HealthState