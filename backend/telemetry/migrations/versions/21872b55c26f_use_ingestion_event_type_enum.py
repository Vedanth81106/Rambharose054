"""use ingestion event type enum

Revision ID: 21872b55c26f
Revises: 826ff0d83aae
Create Date: 2026-08-29 21:32:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "21872b55c26f"
down_revision: Union[str, Sequence[str], None] = "826ff0d83aae"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    event_type_enum = sa.Enum(
        "GAP",
        "OUT_OF_ORDER",
        name="ingestioneventtype",
    )

    event_type_enum.create(op.get_bind())

    op.alter_column(
        "ingestion_events",
        "event_type",
        existing_type=sa.VARCHAR(),
        type_=event_type_enum,
        existing_nullable=False,
        postgresql_using="event_type::text::ingestioneventtype",
    )


def downgrade() -> None:
    event_type_enum = sa.Enum(
        "GAP",
        "OUT_OF_ORDER",
        name="ingestioneventtype",
    )

    op.alter_column(
        "ingestion_events",
        "event_type",
        existing_type=event_type_enum,
        type_=sa.VARCHAR(),
        existing_nullable=False,
    )

    event_type_enum.drop(op.get_bind())