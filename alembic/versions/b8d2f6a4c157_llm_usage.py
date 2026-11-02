"""llm_usage: model calls per local day

Revision ID: b8d2f6a4c157
Revises: f7b2c4e8a915
Create Date: 2026-11-02 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8d2f6a4c157"
down_revision: str | Sequence[str] | None = "f7b2c4e8a915"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_usage",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_usage")),
        sa.UniqueConstraint("day", name=op.f("uq_llm_usage_day")),
    )


def downgrade() -> None:
    op.drop_table("llm_usage")
