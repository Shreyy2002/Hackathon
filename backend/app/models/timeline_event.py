"""
TimelineEvent ORM model — Timeline context (append-only).
Requirements: 2.4, 2.5, 7.1, 13.1

IMPORTANT: This table is append-only. No UPDATE or DELETE operations are
permitted. The application layer enforces this; a DB trigger may reinforce it.
There is intentionally NO updated_at column.
"""
from enum import Enum
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class EventType(str, Enum):
    goal_created = "goal_created"
    goal_submitted = "goal_submitted"
    goal_approved = "goal_approved"
    goal_rejected = "goal_rejected"
    progress_updated = "progress_updated"
    feedback = "feedback"
    achievement = "achievement"
    check_in = "check_in"
    peer_review = "peer_review"
    evidence_tagged = "evidence_tagged"


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id = sa.Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
    )
    employee_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id"),
        nullable=False,
    )
    actor_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id"),
        nullable=False,
    )
    event_type = sa.Column(
        sa.Enum(EventType, name="eventtype", create_type=False),
        nullable=False,
    )
    payload = sa.Column(JSONB, nullable=False)
    linked_goal_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("goals.id"),
        nullable=True,
    )
    created_at = sa.Column(
        sa.DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    is_evidence = sa.Column(sa.Boolean, nullable=False, default=False)

    # NOTE: No updated_at — this table is append-only.

    # User who this event belongs to
    employee = relationship(
        "User",
        foreign_keys=[employee_id],
    )

    # User who performed the action
    actor = relationship(
        "User",
        foreign_keys=[actor_id],
    )

    # Goal this event is linked to (optional)
    linked_goal = relationship(
        "Goal",
        back_populates="timeline_events",
        foreign_keys=[linked_goal_id],
    )
