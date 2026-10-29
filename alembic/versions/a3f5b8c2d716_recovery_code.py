"""recovery code

Revision ID: a3f5b8c2d716
Revises: 7c1d2e4f9a30
Create Date: 2026-10-29 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f5b8c2d716"
down_revision: str | Sequence[str] | None = "7c1d2e4f9a30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("recovery_code_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "users", sa.Column("recovery_code_created_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column("recovery_code_confirmed", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "recovery_code_confirmed")
    op.drop_column("users", "recovery_code_created_at")
    op.drop_column("users", "recovery_code_hash")
