"""
Review ORM model — Reviews context.
Requirements: 2.6, 2.7, 7.1, 13.1
"""
from enum import Enum
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.app.database import Base


class ReviewStatus(str, Enum):
    draft = "draft"
    in_progress = "in_progress"
    submitted = "submitted"
    calibrated = "calibrated"


class Review(Base):
    __tablename__ = "reviews"

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
    manager_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id"),
        nullable=False,
    )
    cycle_name = sa.Column(sa.String, nullable=False)
    ai_draft_text = sa.Column(sa.Text, nullable=True)
    manager_comments = sa.Column(sa.Text, nullable=True)
    # final_rating: 1–5; validated at the application/Pydantic layer
    final_rating = sa.Column(sa.Integer, nullable=True)
    status = sa.Column(
        sa.Enum(ReviewStatus, name="reviewstatus", create_type=False),
        nullable=False,
        default=ReviewStatus.draft,
    )
    manager_override = sa.Column(sa.Text, nullable=True)
    calibration_notes = sa.Column(sa.Text, nullable=True)
    ai_task_id = sa.Column(sa.String, nullable=True)  # Celery task ID
    created_at = sa.Column(
        sa.DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = sa.Column(
        sa.DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    # Employee being reviewed
    employee = relationship(
        "User",
        foreign_keys=[employee_id],
    )

    # Manager who owns this review
    manager = relationship(
        "User",
        foreign_keys=[manager_id],
    )
