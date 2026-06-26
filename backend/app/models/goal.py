"""
Goal ORM model — Goals context.
Requirements: 2.2, 2.3, 7.1, 13.1
"""
from enum import Enum
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, backref

from backend.app.database import Base


class GoalStatus(str, Enum):
    draft = "draft"
    pending_approval = "pending_approval"
    approved = "approved"
    rejected = "rejected"


class GoalHealth(str, Enum):
    on_track = "on_track"
    at_risk = "at_risk"
    off_track = "off_track"


class Goal(Base):
    __tablename__ = "goals"

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
    parent_goal_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("goals.id"),
        nullable=True,
    )
    title = sa.Column(sa.String, nullable=False)
    success_metric = sa.Column(sa.String, nullable=False)
    # Numeric(4, 3) supports values like 0.300, 1.000
    weight = sa.Column(sa.Numeric(4, 3), nullable=False)
    status = sa.Column(
        sa.Enum(GoalStatus, name="goalstatus", create_type=False),
        nullable=False,
        default=GoalStatus.draft,
    )
    progress = sa.Column(sa.Integer, nullable=False, default=0)  # 0–100
    health = sa.Column(
        sa.Enum(GoalHealth, name="goalhealth", create_type=False),
        nullable=False,
        default=GoalHealth.on_track,
    )

    # Relationship to owning employee
    employee = relationship(
        "User",
        back_populates="goals",
        foreign_keys=[employee_id],
    )

    # Self-referential: parent goal -> child goals
    children = relationship(
        "Goal",
        backref=backref("parent", remote_side=[id]),
    )

    # Timeline events linked to this goal
    timeline_events = relationship(
        "TimelineEvent",
        back_populates="linked_goal",
        foreign_keys="TimelineEvent.linked_goal_id",
    )
