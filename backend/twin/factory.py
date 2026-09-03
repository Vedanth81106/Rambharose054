from telemetry.repository import TelemetryRepository

from twin.ml import MLPredictor
from twin.repository import HealthSnapshotRepository
from twin.service import DigitalTwinService


def create_digital_twin_service(
    predictor: MLPredictor,
) -> DigitalTwinService:
    return DigitalTwinService(
        repository=HealthSnapshotRepository(),
        telemetry_repository=TelemetryRepository(),
        predictor=predictor,
    )