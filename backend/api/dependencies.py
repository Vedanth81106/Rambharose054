from collections.abc import Generator

from sqlalchemy.orm import Session

from telemetry.database import SessionLocal
from telemetry.repository import TelemetryRepository
from twin.factory import create_digital_twin_service
from twin.ml_predictor import ModelPredictor
from twin.repository import HealthSnapshotRepository
from twin.service import DigitalTwinService

# Stateless — built once at import time, reused across every request.
_predictor = ModelPredictor()
_twin_service = create_digital_twin_service(_predictor)


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_telemetry_repo() -> TelemetryRepository:
    return TelemetryRepository()


def get_health_snapshot_repo() -> HealthSnapshotRepository:
    return HealthSnapshotRepository()


def get_twin_service() -> DigitalTwinService:
    return _twin_service

# python waste