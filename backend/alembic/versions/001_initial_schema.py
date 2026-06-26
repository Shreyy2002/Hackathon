"""Initial schema — all four tables, indexes, and append-only trigger.

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

Requirements: 7.1, 7.7, 7.8
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Upgrade — create everything from scratch
# ---------------------------------------------------------------------------
def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. PostgreSQL enum types
    #    Created as native DB types so they are shared across sessions and
    #    survive ORM re-creation without conflicts.
    # ------------------------------------------------------------------
    op.execute(sa.text(
        "CREATE TYPE userrole AS ENUM ('employee', 'manager', 'hr')"
    ))
    op.execute(sa.text(
        "CREATE TYPE goalstatus AS ENUM "
        "('draft', 'pending_approval', 'approved', 'rejected')"
    ))
    op.execute(sa.text(
        "CREATE TYPE goalhealth AS ENUM ('on_track', 'at_risk', 'off_track')"
    ))
    op.execute(sa.text(
        "CREATE TYPE eventtype AS ENUM ("
        "'goal_created', 'goal_submitted', 'goal_approved', 'goal_rejected', "
        "'progress_updated', 'feedback', 'achievement', 'check_in', "
        "'peer_review', 'evidence_tagged')"
    ))
    op.execute(sa.text(
        "CREATE TYPE reviewstatus AS ENUM "
        "('draft', 'in_progress', 'submitted', 'calibrated')"
    ))

    # ------------------------------------------------------------------
    # 2. users table
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("employee", "manager", "hr", name="userrole", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "manager_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )

    # ------------------------------------------------------------------
    # 3. goals table
    # ------------------------------------------------------------------
    op.create_table(
        "goals",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "parent_goal_id",
            UUID(as_uuid=True),
            sa.ForeignKey("goals.id"),
            nullable=True,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("success_metric", sa.String(), nullable=False),
        sa.Column("weight", sa.Numeric(4, 3), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft", "pending_approval", "approved", "rejected",
                name="goalstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "progress",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "health",
            sa.Enum(
                "on_track", "at_risk", "off_track",
                name="goalhealth",
                create_type=False,
            ),
            nullable=False,
            server_default="on_track",
        ),
    )

    # ------------------------------------------------------------------
    # 4. timeline_events table (append-only — enforced by trigger below)
    # ------------------------------------------------------------------
    op.create_table(
        "timeline_events",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.Enum(
                "goal_created", "goal_submitted", "goal_approved",
                "goal_rejected", "progress_updated", "feedback",
                "achievement", "check_in", "peer_review", "evidence_tagged",
                name="eventtype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column(
            "linked_goal_id",
            UUID(as_uuid=True),
            sa.ForeignKey("goals.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "is_evidence",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        # NOTE: No updated_at — this table is intentionally append-only.
    )

    # ------------------------------------------------------------------
    # 5. reviews table
    # ------------------------------------------------------------------
    op.create_table(
        "reviews",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "manager_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("cycle_name", sa.String(), nullable=False),
        sa.Column("ai_draft_text", sa.Text(), nullable=True),
        sa.Column("manager_comments", sa.Text(), nullable=True),
        sa.Column("final_rating", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft", "in_progress", "submitted", "calibrated",
                name="reviewstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("manager_override", sa.Text(), nullable=True),
        sa.Column("calibration_notes", sa.Text(), nullable=True),
        sa.Column("ai_task_id", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------
    # 6. Indexes on timeline_events (Requirement 7.7)
    # ------------------------------------------------------------------
    op.execute(sa.text(
        "CREATE INDEX ix_timeline_employee_created "
        "ON timeline_events(employee_id, created_at DESC)"
    ))
    op.execute(sa.text(
        "CREATE INDEX ix_timeline_event_type "
        "ON timeline_events(event_type)"
    ))

    # ------------------------------------------------------------------
    # 7. Append-only trigger — prevent UPDATE and DELETE on timeline_events
    #    (Requirement 7.8)
    # ------------------------------------------------------------------
    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION prevent_timeline_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
          RAISE EXCEPTION 'timeline_events is append-only';
        END;
        $$ LANGUAGE plpgsql
    """))

    op.execute(sa.text("""
        CREATE TRIGGER enforce_append_only
        BEFORE UPDATE OR DELETE ON timeline_events
        FOR EACH ROW EXECUTE FUNCTION prevent_timeline_mutation()
    """))


# ---------------------------------------------------------------------------
# Downgrade — tear everything down in reverse dependency order
# ---------------------------------------------------------------------------
def downgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Remove the append-only trigger and its function
    # ------------------------------------------------------------------
    op.execute(sa.text(
        "DROP TRIGGER IF EXISTS enforce_append_only ON timeline_events"
    ))
    op.execute(sa.text(
        "DROP FUNCTION IF EXISTS prevent_timeline_mutation()"
    ))

    # ------------------------------------------------------------------
    # 2. Drop indexes
    # ------------------------------------------------------------------
    op.execute(sa.text("DROP INDEX IF EXISTS ix_timeline_event_type"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_timeline_employee_created"))

    # ------------------------------------------------------------------
    # 3. Drop tables in FK-safe order (children before parents)
    # ------------------------------------------------------------------
    op.drop_table("reviews")
    op.drop_table("timeline_events")
    op.drop_table("goals")
    op.drop_table("users")

    # ------------------------------------------------------------------
    # 4. Drop enum types
    # ------------------------------------------------------------------
    op.execute(sa.text("DROP TYPE IF EXISTS reviewstatus"))
    op.execute(sa.text("DROP TYPE IF EXISTS eventtype"))
    op.execute(sa.text("DROP TYPE IF EXISTS goalhealth"))
    op.execute(sa.text("DROP TYPE IF EXISTS goalstatus"))
    op.execute(sa.text("DROP TYPE IF EXISTS userrole"))
