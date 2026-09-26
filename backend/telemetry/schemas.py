from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class TelemetryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime

    engine_id: str
    mission_id: str

    rpm: float
    torque: float
    cht: float
    egt: float

    oil_pressure: float
    oil_temperature: float

    fuel_flow: float
    vibration: float
    
    throttle: float
    engine_load: float
    altitude: float
    ambient_temperature: float

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include timezone information")

        return value