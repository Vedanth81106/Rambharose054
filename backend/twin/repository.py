from sqlalchemy import select
from sqlalchemy.orm import Session

from twin.models import HealthSnapshot


class HealthSnapshotRepository:

    def save(
        self,
        session: Session,
        snapshot: HealthSnapshot,
    ) -> HealthSnapshot:
        session.add(snapshot)
        session.flush()

        return snapshot

    def get_by_engine(
        self,
        session: Session,
        engine_id: str,
    ) -> list[HealthSnapshot]:
        statement = (
            select(HealthSnapshot)
            .where(HealthSnapshot.engine_id == engine_id)
            .order_by(HealthSnapshot.time)
        )

        return list(session.scalars(statement))