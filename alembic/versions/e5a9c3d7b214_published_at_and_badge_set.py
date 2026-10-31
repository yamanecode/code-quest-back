"""published_at on missions and challenges, badge set, no daily assignments

Revision ID: e5a9c3d7b214
Revises: d4e8a1b6c593
Create Date: 2026-10-31 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5a9c3d7b214"
down_revision: str | Sequence[str] | None = "d4e8a1b6c593"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Badge codes that are not in the badge list any more; their earned rows go with them.
DROPPED_BADGES = (
    "streak_3",
    "streak_7",
    "streak_14",
    "daily_7",
    "no_hint_mission",
    "level_5",
    "level_8",
    "first_try_20",
)


def upgrade() -> None:
    for table in ("missions", "challenges"):
        op.add_column(table, sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    # Content already published counts as published when it was created.
    op.execute("UPDATE missions SET published_at = created_at WHERE status = 'published'")
    op.execute("UPDATE challenges SET published_at = created_at WHERE status = 'published'")

    dropped = sa.bindparam("codes", value=list(DROPPED_BADGES), expanding=True)
    op.get_bind().execute(
        sa.text(
            "DELETE FROM user_badges WHERE badge_id IN (SELECT id FROM badges WHERE code IN :codes)"
        ).bindparams(dropped)
    )
    op.get_bind().execute(sa.text("DELETE FROM badges WHERE code IN :codes").bindparams(dropped))

    op.drop_table("daily_assignments")


def downgrade() -> None:
    op.create_table(
        "daily_assignments",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("challenge_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["challenge_id"],
            ["challenges.id"],
            name=op.f("fk_daily_assignments_challenge_id_challenges"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_daily_assignments_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_assignments")),
        sa.UniqueConstraint("user_id", "day", name=op.f("uq_daily_assignments_user_id_day")),
    )
    # The dropped badge rows are not restored; the seed commands sync the badge list.
    op.drop_column("challenges", "published_at")
    op.drop_column("missions", "published_at")
