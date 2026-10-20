"""baseline

Revision ID: 553b94e9735a
Revises:
Create Date: 2026-10-20 04:23:01.328850

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "553b94e9735a"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "badges",
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("tier", sa.Enum("bronze", "silver", "gold", name="badge_tier"), nullable=False),
        sa.Column("emoji", sa.String(length=16), nullable=False),
        sa.Column("hidden", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_badges")),
        sa.UniqueConstraint("code", name=op.f("uq_badges_code")),
    )
    op.create_table(
        "users",
        sa.Column("username", sa.String(length=30), nullable=False),
        sa.Column("password_hash", sa.String(length=100), nullable=False),
        sa.Column(
            "role", sa.Enum("student", "professor", "system", name="user_role"), nullable=False
        ),
        sa.Column("profile_public", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )
    op.create_table(
        "challenges",
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=80), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("ordering", "grouping", "filtering", "pattern", name="challenge_type"),
            nullable=False,
        ),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("status", sa.Enum("draft", "published", name="content_status"), nullable=False),
        sa.Column(
            "origin", sa.Enum("professor", "ai", "base", name="challenge_origin"), nullable=False
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_challenges_owner_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_challenges")),
    )
    op.create_table(
        "classrooms",
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("join_code", sa.String(length=6), nullable=False),
        sa.Column("professor_id", sa.Integer(), nullable=False),
        sa.Column("weekly_goal", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "weekly_goal BETWEEN 1 AND 1000", name=op.f("ck_classrooms_weekly_goal_range")
        ),
        sa.ForeignKeyConstraint(
            ["professor_id"], ["users.id"], name=op.f("fk_classrooms_professor_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_classrooms")),
        sa.UniqueConstraint("join_code", name=op.f("uq_classrooms_join_code")),
    )
    op.create_table(
        "user_badges",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("badge_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["badge_id"], ["badges.id"], name=op.f("fk_user_badges_badge_id_badges")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_badges_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_badges")),
        sa.UniqueConstraint("user_id", "badge_id", name=op.f("uq_user_badges_user_id_badge_id")),
    )
    op.create_table(
        "class_goal_rewards",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("classroom_id", sa.Integer(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["classroom_id"],
            ["classrooms.id"],
            name=op.f("fk_class_goal_rewards_classroom_id_classrooms"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_class_goal_rewards_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_class_goal_rewards")),
        sa.UniqueConstraint(
            "user_id",
            "classroom_id",
            "week_start",
            name=op.f("uq_class_goal_rewards_user_id_classroom_id_week_start"),
        ),
    )
    op.create_table(
        "classroom_members",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("classroom_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["classroom_id"],
            ["classrooms.id"],
            name=op.f("fk_classroom_members_classroom_id_classrooms"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_classroom_members_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_classroom_members")),
        sa.UniqueConstraint(
            "user_id", "classroom_id", name=op.f("uq_classroom_members_user_id_classroom_id")
        ),
    )
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
    op.create_table(
        "hint_events",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("challenge_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.Enum("request", "after_wrong", name="hint_source"), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("discarded_count", sa.Integer(), nullable=False),
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
            name=op.f("fk_hint_events_challenge_id_challenges"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_hint_events_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hint_events")),
    )
    op.create_table(
        "missions",
        sa.Column("classroom_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=400), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        # content_status was already created with the challenges table.
        sa.Column(
            "status",
            postgresql.ENUM("draft", "published", name="content_status", create_type=False),
            nullable=False,
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["classroom_id"], ["classrooms.id"], name=op.f("fk_missions_classroom_id_classrooms")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_missions")),
    )
    op.create_table(
        "submissions",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("challenge_id", sa.Integer(), nullable=False),
        sa.Column("answer", sa.JSON(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["challenge_id"], ["challenges.id"], name=op.f("fk_submissions_challenge_id_challenges")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_submissions_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_submissions")),
    )
    op.create_index(
        "ix_submissions_user_id_challenge_id",
        "submissions",
        ["user_id", "challenge_id"],
        unique=False,
    )
    op.create_table(
        "xp_events",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("challenge_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=30), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["challenge_id"], ["challenges.id"], name=op.f("fk_xp_events_challenge_id_challenges")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_xp_events_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_xp_events")),
        sa.UniqueConstraint(
            "user_id",
            "challenge_id",
            "reason",
            name=op.f("uq_xp_events_user_id_challenge_id_reason"),
        ),
    )
    op.create_table(
        "mission_challenges",
        sa.Column("mission_id", sa.Integer(), nullable=False),
        sa.Column("challenge_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
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
            name=op.f("fk_mission_challenges_challenge_id_challenges"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["mission_id"],
            ["missions.id"],
            name=op.f("fk_mission_challenges_mission_id_missions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mission_challenges")),
        sa.UniqueConstraint(
            "mission_id", "challenge_id", name=op.f("uq_mission_challenges_mission_id_challenge_id")
        ),
    )


def downgrade() -> None:
    op.drop_table("mission_challenges")
    op.drop_table("xp_events")
    op.drop_index("ix_submissions_user_id_challenge_id", table_name="submissions")
    op.drop_table("submissions")
    op.drop_table("missions")
    op.drop_table("hint_events")
    op.drop_table("daily_assignments")
    op.drop_table("classroom_members")
    op.drop_table("class_goal_rewards")
    op.drop_table("user_badges")
    op.drop_table("classrooms")
    op.drop_table("challenges")
    op.drop_table("users")
    op.drop_table("badges")
    for enum_name in (
        "badge_tier",
        "user_role",
        "challenge_type",
        "content_status",
        "challenge_origin",
        "hint_source",
    ):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
