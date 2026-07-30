"""create user health profiles

Revision ID: 202607300004
Revises: 202607240003
Create Date: 2026-07-30

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "202607300004"
down_revision: str | None = "202607240003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    gender = postgresql.ENUM(
        "MALE",
        "FEMALE",
        "OTHER",
        "PREFER_NOT_TO_SAY",
        name="health_profile_gender",
        create_type=False,
    )
    activity_level = postgresql.ENUM(
        "SEDENTARY",
        "LIGHT",
        "MODERATE",
        "ACTIVE",
        "VERY_ACTIVE",
        name="health_profile_activity_level",
        create_type=False,
    )
    primary_goal = postgresql.ENUM(
        "MAINTAIN",
        "WEIGHT_LOSS",
        "WEIGHT_GAIN",
        "MUSCLE_GAIN",
        name="health_profile_primary_goal",
        create_type=False,
    )
    preference_type = postgresql.ENUM(
        "ALLERGY",
        "DIETARY_RESTRICTION",
        "TASTE",
        "DISLIKE",
        name="health_profile_preference_type",
        create_type=False,
    )
    gender.create(op.get_bind(), checkfirst=True)
    activity_level.create(op.get_bind(), checkfirst=True)
    primary_goal.create(op.get_bind(), checkfirst=True)
    preference_type.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "users",
        sa.Column(
            "profile_onboarding_dismissed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_table(
        "health_profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("gender", gender, nullable=False),
        sa.Column("weight_kg", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("height_cm", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("activity_level", activity_level, nullable=False),
        sa.Column("primary_goal", primary_goal, nullable=False),
        sa.Column(
            "target_weight_kg",
            sa.Numeric(precision=6, scale=2),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "height_cm > 0",
            name=op.f("ck_health_profiles_health_profiles_height_positive"),
        ),
        sa.CheckConstraint(
            "target_weight_kg IS NULL OR target_weight_kg > 0",
            name=op.f(
                "ck_health_profiles_health_profiles_target_weight_positive"
            ),
        ),
        sa.CheckConstraint(
            "weight_kg > 0",
            name=op.f("ck_health_profiles_health_profiles_weight_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_health_profiles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_health_profiles")),
    )

    op.create_table(
        "health_profile_preferences",
        sa.Column(
            "preference_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("preference_type", preference_type, nullable=False),
        sa.Column("value", sa.String(length=100), nullable=False),
        sa.Column("normalized_value", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name=op.f("fk_health_profile_preferences_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "preference_id",
            name=op.f("pk_health_profile_preferences"),
        ),
        sa.UniqueConstraint(
            "user_id",
            "preference_type",
            "normalized_value",
            name="uq_health_profile_preferences_owner_type_value",
        ),
    )
    op.create_index(
        op.f("ix_health_profile_preferences_user_id"),
        "health_profile_preferences",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_health_profile_preferences_user_id"),
        table_name="health_profile_preferences",
    )
    op.drop_table("health_profile_preferences")
    op.drop_table("health_profiles")
    op.drop_column("users", "profile_onboarding_dismissed_at")

    postgresql.ENUM(
        "ALLERGY",
        "DIETARY_RESTRICTION",
        "TASTE",
        "DISLIKE",
        name="health_profile_preference_type",
        create_type=False,
    ).drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(
        "MAINTAIN",
        "WEIGHT_LOSS",
        "WEIGHT_GAIN",
        "MUSCLE_GAIN",
        name="health_profile_primary_goal",
        create_type=False,
    ).drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(
        "SEDENTARY",
        "LIGHT",
        "MODERATE",
        "ACTIVE",
        "VERY_ACTIVE",
        name="health_profile_activity_level",
        create_type=False,
    ).drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(
        "MALE",
        "FEMALE",
        "OTHER",
        "PREFER_NOT_TO_SAY",
        name="health_profile_gender",
        create_type=False,
    ).drop(op.get_bind(), checkfirst=True)
