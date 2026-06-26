"""
Employees router — employee profile endpoint.
Requirements: 2.1, 13.1
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.goal import Goal
from app.models.timeline_event import TimelineEvent
from app.models.user import User
from app.schemas.user import EmployeeProfileRead, GoalReadBrief, TimelineEventBrief, UserRead

router = APIRouter(tags=["employees"])


@router.get("/employees/{employee_id}/profile", response_model=EmployeeProfileRead)
async def get_employee_profile(
    employee_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> EmployeeProfileRead:
    """
    Return an aggregated employee profile in a single round-trip:
    - User info
    - All goals
    - 20 most recent timeline events
    """
    user = await db.get(User, employee_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )

    # Load all goals for this employee
    goals_stmt = select(Goal).where(Goal.employee_id == employee_id)
    goals = (await db.execute(goals_stmt)).scalars().all()

    # Load 20 most recent timeline events for this employee
    events_stmt = (
        select(TimelineEvent)
        .where(TimelineEvent.employee_id == employee_id)
        .order_by(TimelineEvent.created_at.desc())
        .limit(20)
    )
    events = (await db.execute(events_stmt)).scalars().all()

    return EmployeeProfileRead(
        user=UserRead.model_validate(user),
        goals=[GoalReadBrief.model_validate(g) for g in goals],
        recent_events=[TimelineEventBrief.model_validate(e) for e in events],
    )
