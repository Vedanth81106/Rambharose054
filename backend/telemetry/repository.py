from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from models import IngestionEvent, Telemetry

class TelemetryRepository:

    def save(
        self,
        session: Session,
        telemetry: Telemetry,
    ) -> bool:
        statement = insert(Telemetry).values(
            time=telemetry.time,
            received_at=telemetry.received_at,
            engine_id=telemetry.engine_id,
            mission_id=telemetry.mission_id,
            rpm=telemetry.rpm,
            cht=telemetry.cht,
            egt=telemetry.egt,
            oil_pressure=telemetry.oil_pressure,
            oil_temperature=telemetry.oil_temperature,
            fuel_flow=telemetry.fuel_flow,
            vibration=telemetry.vibration,
            battery_voltage=telemetry.battery_voltage,
            alternator_current=telemetry.alternator_current,
            injection_timing=telemetry.injection_timing,
        )

        statement = statement.on_conflict_do_nothing(
            constraint="uq_telemetry_event",
        )

        result = session.execute(
            statement.returning(Telemetry.id)
        )

        return result.scalar_one_or_none() is not None

    def get_by_mission(
        self,
        session: Session,
        mission_id: str,
    ) -> list[Telemetry]:
        statement = (
            select(Telemetry)
            .where(Telemetry.mission_id == mission_id)
            .order_by(Telemetry.time)
        )

        return list(session.scalars(statement))
    
    def save_ingestion_event(
        self,
        session: Session,
        event: IngestionEvent,
    ) -> IngestionEvent:
        session.add(event)
        session.flush()

        return event
    
    def get_latest_window(
        self,
        session: Session,
        engine_id: str,
        mission_id: str,
        limit: int = 60,
    ) -> list[Telemetry]:
        statement = (
            select(Telemetry)
            .where(
                Telemetry.engine_id == engine_id,
                Telemetry.mission_id == mission_id,
            )
            .order_by(Telemetry.time.desc())
            .limit(limit)
        )

        telemetry = list(session.scalars(statement))

        return list(reversed(telemetry))
    
    def get_latest_timestamp(
        self,
        session: Session,
        engine_id: str,
        mission_id: str,
    ):
        statement = (
            select(Telemetry.time)
            .where(
                Telemetry.engine_id == engine_id,
                Telemetry.mission_id == mission_id,
            )
            .order_by(Telemetry.time.desc())
            .limit(1)
        )

        return session.scalar(statement)
    
    def exists(
        self,
        session: Session,
        engine_id: str,
        mission_id: str,
        timestamp,
    ) -> bool:
        statement = (
            select(Telemetry.id)
            .where(
                Telemetry.engine_id == engine_id,
                Telemetry.mission_id == mission_id,
                Telemetry.time == timestamp,
            )
            .limit(1)
        )

        return session.scalar(statement) is not None
    
    def get_ingestion_events(
        self,
        session: Session,
        engine_id: str,
        mission_id: str,
    ) -> list[IngestionEvent]:
        statement = (
            select(IngestionEvent)
            .where(
                IngestionEvent.engine_id == engine_id,
                IngestionEvent.mission_id == mission_id,
            )
            .order_by(IngestionEvent.event_time)
        )

        return list(session.scalars(statement))
    
    def get_by_time_range(
        self,
        session: Session,
        engine_id: str,
        mission_id: str,
        start_time,
        end_time,
    ) -> list[Telemetry]:
        statement = (
            select(Telemetry)
            .where(
                Telemetry.engine_id == engine_id,
                Telemetry.mission_id == mission_id,
                Telemetry.time >= start_time,
                Telemetry.time <= end_time,
            )
            .order_by(Telemetry.time)
        )

        return list(session.scalars(statement))
    
    def get_latest(
        self,
        session: Session,
        engine_id: str,
        mission_id: str,
    ) -> Telemetry | None:
        statement = (
            select(Telemetry)
            .where(
                Telemetry.engine_id == engine_id,
                Telemetry.mission_id == mission_id,
            )
            .order_by(Telemetry.time.desc())
            .limit(1)
        )

        return session.scalar(statement)

    def get_distinct_engines(
        self,
        session: Session,
    ) -> list[str]:
        statement = select(Telemetry.engine_id).distinct()
        return list(session.scalars(statement))

    def get_distinct_missions(
        self,
        session: Session,
    ) -> list[str]:
        statement = select(Telemetry.mission_id).distinct()
        return list(session.scalars(statement))