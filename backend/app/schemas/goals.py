"""
Goal Pydantic schemas — Goals context.
Requirements: 2.1, 2.2, 2.3, 2.4
"""
from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GoalStatus(str, Enum):
    draft = "draft"
    pending_approval = "pending_approval"
    approved = "approved"
    rejected = "rejected"


class GoalHealth(str, Enum):
    on_track = "on_track"
    at_risk = "at_risk"
    off_track = "off_track"


class GoalCreate(BaseModel):
    employee_id: UUID
    parent_goal_id: Optional[UUID] = None
    title: str
    success_metric: str
    # weight must be positive and at most 1.0
    weight: Decimal = Field(..., gt=0, le=1)


class GoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    parent_goal_id: Optional[UUID]
    title: str
    success_metric: str
    weight: Decimal
    status: GoalStatus
    progress: int
    health: GoalHealth
    children: List["GoalRead"] = []


# Rebuild to resolve the forward reference on children
GoalRead.model_rebuild()


class GoalProgressUpdate(BaseModel):
    progress: int = Field(..., ge=0, le=100)
    health: GoalHealth
    note: Optional[str] = None


class GoalListResponse(BaseModel):
    goals: List[GoalRead]
    performance_score: Decimal
