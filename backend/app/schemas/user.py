"""
Pydantic v2 schemas — Identity context.
Requirements: 2.1, 7.1, 13.1
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserRole(str, Enum):
    employee = "employee"
    manager = "manager"
    hr = "hr"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    role: UserRole
    manager_id: Optional[UUID] = None


class RoleSwitchRequest(BaseModel):
    user_id: UUID


class GoalReadBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    status: str
    progress: int
    health: str
    weight: float


class TimelineEventBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: str
    payload: dict
    created_at: datetime
    is_evidence: bool


class EmployeeProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: UserRead
    goals: List[GoalReadBrief]
    recent_events: List[TimelineEventBrief]
