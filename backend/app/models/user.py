"""
User ORM model — Identity context.
Requirements: 2.1, 7.1, 13.1
"""
from enum import Enum
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, backref

from app.database import Base


class UserRole(str, Enum):
    employee = "employee"
    manager = "manager"
    hr = "hr"


class User(Base):
    __tablename__ = "users"

    id = sa.Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
    )
    name = sa.Column(sa.String, nullable=False)
    role = sa.Column(
        sa.Enum(UserRole, name="userrole", create_type=False),
        nullable=False,
    )
    manager_id = sa.Column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id"),
        nullable=True,
    )

    # Self-referential: one manager -> many direct reports
    direct_reports = relationship(
        "User",
        backref=backref("manager", remote_side=[id]),
    )

    # Goals owned by this user as employee
    goals = relationship(
        "Goal",
        back_populates="employee",
        foreign_keys="Goal.employee_id",
    )
