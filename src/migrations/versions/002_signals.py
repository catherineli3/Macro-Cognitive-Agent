"""002_signals — Create signals table for Sprint 2 Signal Engine.

Table: signals
  - id: auto-increment primary key
  - signal_id: unique signal identifier (indexed)
  - indicator: symbol that generated this signal (indexed)
  - dimension: hypothesis dimension (indexed)
  - direction: bullish | bearish | neutral
  - strength: strong | moderate | weak
  - confidence: float 0-1
  - timestamp: signal generation time (indexed)
  - data_timestamp: timestamp of input data
  - evidence_json: JSON-encoded list of SignalEvidence
  - interpretation_summary: concatenated interpretation strings
  - ingested_at: when signal was persisted
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "signals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("signal_id", sa.String(32), nullable=False),
        sa.Column("indicator", sa.String(20), nullable=False),
        sa.Column("dimension", sa.String(30), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("strength", sa.String(10), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("interpretation_summary", sa.String(500), nullable=True, server_default=""),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signal_id", "signals", ["signal_id"])
    op.create_index("ix_indicator", "signals", ["indicator"])
    op.create_index("ix_dimension", "signals", ["dimension"])
    op.create_index("ix_signal_timestamp", "signals", ["timestamp"])
    op.create_index("ix_indicator_timestamp", "signals", ["indicator", "timestamp"])


def downgrade() -> None:
    op.drop_index("ix_indicator_timestamp", table_name="signals")
    op.drop_index("ix_signal_timestamp", table_name="signals")
    op.drop_index("ix_dimension", table_name="signals")
    op.drop_index("ix_indicator", table_name="signals")
    op.drop_index("ix_signal_id", table_name="signals")
    op.drop_table("signals")
