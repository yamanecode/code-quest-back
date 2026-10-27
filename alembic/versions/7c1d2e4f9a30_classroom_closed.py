"""classroom closed flag

Revision ID: 7c1d2e4f9a30
Revises: 553b94e9735a
Create Date: 2026-10-27 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c1d2e4f9a30"
down_revision: str | Sequence[str] | None = "553b94e9735a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "classrooms",
        sa.Column("closed", sa.Boolean(), server_default="false", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("classrooms", "closed")
