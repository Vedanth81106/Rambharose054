"""create telemetry table

Revision ID: 13f677398608
Revises:
Create Date: 2026-08-29 13:54:13.480477

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "13f677398608"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "telemetry",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "time",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "engine_id",
            sa.String(),
            nullable=False,
        ),
        sa.Column(
            "mission_id",
            sa.String(),
            nullable=False,
        ),
        sa.Column("rpm", sa.Float(), nullable=False),
        sa.Column("cht", sa.Float(), nullable=False),
        sa.Column("egt", sa.Float(), nullable=False),
        sa.Column(
            "oil_pressure",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "oil_temperature",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "fuel_flow",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "vibration",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "battery_voltage",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "alternator_current",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "injection_timing",
            sa.Float(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", "time"),
        sa.UniqueConstraint(
            "engine_id",
            "mission_id",
            "time",
            name="uq_telemetry_event",
        ),
    )

    op.execute(
        """
        SELECT create_hypertable(
            'telemetry',
            by_range('time'),
            if_not_exists => TRUE
        );
        """
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_table("telemetry")
