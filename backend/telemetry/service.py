from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models import IngestionEvent, IngestionEventType, Telemetry
from repository import TelemetryRepository
from schemas import TelemetryCreate


MAX_FUTURE_SECONDS = 30
GAP_THRESHOLD_SECONDS = 2


class TelemetryService:

    def __init__(self, repository: TelemetryRepository):
        self.repository = repository

    def process(
        self,
        session: Session,
        data: TelemetryCreate,
        topic: str,
    ) -> bool:

        engine_id = self._extract_engine_id(topic)

        if engine_id != data.engine_id:
            raise ValueError(
                "engine_id does not match MQTT topic"
            )

        now = datetime.now(timezone.utc)

        if data.timestamp > now:
            future_seconds = (
                data.timestamp - now
            ).total_seconds()

            if future_seconds > MAX_FUTURE_SECONDS:
                raise ValueError(
                    "telemetry timestamp is too far "
                    "in the future"
                )

        if self.repository.exists(
            session,
            data.engine_id,
            data.mission_id,
            data.timestamp,
        ):
            return False

        previous_timestamp = (
            self.repository.get_latest_timestamp(
                session,
                data.engine_id,
                data.mission_id,
            )
        )

        if previous_timestamp is not None:
            self._check_timestamp_order(
                session,
                data,
                previous_timestamp,
                now,
            )

        telemetry = Telemetry(
            time=data.timestamp,
            received_at=now,
            engine_id=data.engine_id,
            mission_id=data.mission_id,
            rpm=data.rpm,
            cht=data.cht,
            egt=data.egt,
            oil_pressure=data.oil_pressure,
            oil_temperature=data.oil_temperature,
            fuel_flow=data.fuel_flow,
            vibration=data.vibration,
            battery_voltage=data.battery_voltage,
            alternator_current=data.alternator_current,
            injection_timing=data.injection_timing,
        )

        return self.repository.save(session, telemetry)

    def _check_timestamp_order(
        self,
        session: Session,
        data: TelemetryCreate,
        previous_timestamp: datetime,
        detected_at: datetime,
    ) -> None:

        interval = (
            data.timestamp - previous_timestamp
        ).total_seconds()

        if interval < 0:
            event = IngestionEvent(
                engine_id=data.engine_id,
                mission_id=data.mission_id,
                event_type=IngestionEventType.OUT_OF_ORDER,
                event_time=data.timestamp,
                detected_at=detected_at,
                details=(
                    f"Telemetry timestamp {data.timestamp} "
                    f"arrived after {previous_timestamp}"
                ),
            )

            self.repository.save_ingestion_event(
                session,
                event,
            )

        elif interval > GAP_THRESHOLD_SECONDS:
            event = IngestionEvent(
                engine_id=data.engine_id,
                mission_id=data.mission_id,
                event_type=IngestionEventType.GAP,
                event_time=data.timestamp,
                detected_at=detected_at,
                details=(
                    f"{interval:.1f} seconds between "
                    f"telemetry packets"
                ),
            )

            self.repository.save_ingestion_event(
                session,
                event,
            )

    @staticmethod
    def _extract_engine_id(topic: str) -> str:
        parts = topic.split("/")

        if (
            len(parts) != 3
            or parts[0] != "engine"
            or parts[2] != "telemetry"
        ):
            raise ValueError("invalid MQTT topic")

        return parts[1]