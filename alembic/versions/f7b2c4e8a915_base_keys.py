"""base_key on missions and challenges

Revision ID: f7b2c4e8a915
Revises: e5a9c3d7b214
Create Date: 2026-11-02 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7b2c4e8a915"
down_revision: str | Sequence[str] | None = "e5a9c3d7b214"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("missions", "challenges")


def upgrade() -> None:
    # Only the columns: load-base fills the keys of existing base rows (spec 11).
    for table in TABLES:
        op.add_column(table, sa.Column("base_key", sa.String(length=80), nullable=True))
        op.create_unique_constraint(f"uq_{table}_base_key", table, ["base_key"])


def downgrade() -> None:
    for table in TABLES:
        op.drop_constraint(f"uq_{table}_base_key", table, type_="unique")
        op.drop_column(table, "base_key")
