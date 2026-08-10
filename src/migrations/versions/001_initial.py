"""001_initial — Create macro_observations table.

This is the initial schema migration for Sprint 1.

Table: macro_observations
  - id: auto-increment primary key
  - symbol: ticker identifier (indexed)
  - timestamp: observation datetime with timezone (indexed)
  - value: float observation value
  - currency: currency code
  - unit: unit of measurement
  - source: data source name
  - quality_score: float 0-1 quality assessment
  - ingested_at: pipeline ingestion timestamp with timezone
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "macro_observations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("quality_score", sa.Float(), server_default="1.0", nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_symbol", "macro_observations", ["symbol"])
    op.create_index("ix_timestamp", "macro_observations", ["timestamp"])
    op.create_index("ix_symbol_timestamp", "macro_observations", ["symbol", "timestamp"])


def downgrade() -> None:
    op.drop_index("ix_symbol_timestamp", table_name="macro_observations")
    op.drop_index("ix_timestamp", table_name="macro_observations")
    op.drop_index("ix_symbol", table_name="macro_observations")
    op.drop_table("macro_observations")
