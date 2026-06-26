"""
Goals router — CRUD and approval state machine.
Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2,
              5.1, 5.2, 18.1, 18.2
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.goal import Goal
from app.models.goal import GoalStatus as ModelGoalStatus
from app.models.goal import GoalHealth as ModelGoalHealth
from app.models.timeline_event import EventType
from app.models.user import User
from app.schemas.goals import (
    GoalCreate,
    GoalListResponse,
    GoalProgressUpdate,
    GoalRead,
)
from app.services.goal_service import (
    compute_performance_score,
    get_total_goal_weight,
)
from app.services.timeline_service import append_event

router = APIRouter(prefix="/goals", tags=["goals"])

# ---------------------------------------------------------------------------
# Valid state transitions — Requirements 3.1
# ---------------------------------------------------------------------------
VALID_TRANSITIONS: dict[ModelGoalStatus, set[ModelGoalStatus]] = {
    ModelGoalStatus.draft: {ModelGoalStatus.pending_approval},
    ModelGoalStatus.pending_approval: {
        ModelGoalStatus.approved,
        ModelGoalStatus.rejected,
    },
    ModelGoalStatus.approved: set(),
    ModelGoalStatus.rejected: {ModelGoalStatus.draft},
}


def _assert_transition(goal: Goal, target: ModelGoalStatus) -> None:
    """Raise HTTP 400 if the requested transition is not valid."""
    allowed = VALID_TRANSITIONS.get(goal.status, set())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid state transition: '{goal.status}' → '{target}'. "
                f"Allowed transitions from '{goal.status}': "
                f"{[s.value for s in allowed] or 'none'}."
            ),
        )


# ---------------------------------------------------------------------------
# POST /goals — create a new goal
# ---------------------------------------------------------------------------
@router.post("", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
async def create_goal(
    body: GoalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GoalRead:
    """
    Create a new goal for an employee.

    - Rejects with 400 if adding the weight would exceed 1.0.
    - Rejects with 404 if parent_goal_id is provided but does not reference
      an existing goal owned by the same employee.
    - Appends a goal_created timeline event atomically.
    """
    # Weight guard — Requirements 2.1, 18.1
    current_weight = await get_total_goal_weight(db, body.employee_id)
    if current_weight + body.weight > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Total goal weight would exceed 1.0. "
                f"Current allocated: {current_weight}"
            ),
        )

    # Parent goal validation — Requirements 2.4, 2.5
    if body.parent_goal_id is not None:
        parent = await db.get(Goal, body.parent_goal_id)
        if parent is None or parent.employee_id != body.employee_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent goal not found or does not belong to this employee.",
            )

    # Create goal with defaults — Requirements 2.3
    goal = Goal(
        employee_id=body.employee_id,
        parent_goal_id=body.parent_goal_id,
        title=body.title,
        success_metric=body.success_metric,
        weight=body.weight,
        status=ModelGoalStatus.draft,
        progress=0,
        health=ModelGoalHealth.on_track,
    )
    db.add(goal)
    await db.flush()  # get goal.id before appending the event

    # Append goal_created event — Requirements 2.2, 16.1
    await append_event(
        db=db,
        employee_id=body.employee_id,
        actor_id=current_user.id,
        event_type=EventType.goal_created,
        payload={
            "goal_id": str(goal.id),
            "title": goal.title,
            "status": goal.status.value,
        },
        linked_goal_id=goal.id,
    )

    await db.commit()
    await db.refresh(goal)
    return GoalRead.model_validate(goal)


# ---------------------------------------------------------------------------
# GET /goals/{goal_id} — retrieve a single goal
# ---------------------------------------------------------------------------
@router.get("/{goal_id}", response_model=GoalRead)
async def get_goal(
    goal_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GoalRead:
    """Return a single goal by ID. Raises 404 if not found."""
    goal = await db.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found.",
        )
    return GoalRead.model_validate(goal)


# ---------------------------------------------------------------------------
# GET /goals — list all goals for an employee + performance score
# ---------------------------------------------------------------------------
@router.get("", response_model=GoalListResponse)
async def list_goals(
    employee_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GoalListResponse:
    """
    Return all goals for an employee alongside their computed performance score.
    """
    result = await db.execute(
        select(Goal).where(Goal.employee_id == employee_id)
    )
    goals = list(result.scalars().all())
    score = compute_performance_score(goals)
    return GoalListResponse(
        goals=[GoalRead.model_validate(g) for g in goals],
        performance_score=score,
    )


# ---------------------------------------------------------------------------
# PATCH /goals/{goal_id}/submit — draft → pending_approval
# ---------------------------------------------------------------------------
@router.patch("/{goal_id}/submit", response_model=GoalRead)
async def submit_goal(
    goal_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GoalRead:
    """
    Transition goal from draft → pending_approval.
    Appends a goal_submitted timeline event.
    Requirements: 3.1, 3.2, 7.2, 17.3
    """
    goal = await db.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found.",
        )

    _assert_transition(goal, ModelGoalStatus.pending_approval)
    goal.status = ModelGoalStatus.pending_approval

    await append_event(
        db=db,
        employee_id=goal.employee_id,
        actor_id=current_user.id,
        event_type=EventType.goal_submitted,
        payload={
            "goal_id": str(goal.id),
            "title": goal.title,
            "status": goal.status.value,
        },
        linked_goal_id=goal.id,
    )

    await db.commit()
    await db.refresh(goal)
    return GoalRead.model_validate(goal)


# ---------------------------------------------------------------------------
# PATCH /goals/{goal_id}/approve — pending_approval → approved (manager only)
# ---------------------------------------------------------------------------
class ApproveBody(BaseModel):
    note: Optional[str] = None


@router.patch("/{goal_id}/approve", response_model=GoalRead)
async def approve_goal(
    goal_id: UUID,
    body: ApproveBody = ApproveBody(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GoalRead:
    """
    Transition goal from pending_approval → approved. Manager-only.
    Appends a goal_approved timeline event.
    Requirements: 3.1, 3.3, 3.5, 7.2, 17.1
    """
    goal = await db.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found.",
        )

    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers may approve goals.",
        )

    _assert_transition(goal, ModelGoalStatus.approved)
    goal.status = ModelGoalStatus.approved

    payload: dict = {
        "goal_id": str(goal.id),
        "title": goal.title,
        "status": goal.status.value,
    }
    if body.note is not None:
        payload["note"] = body.note

    await append_event(
        db=db,
        employee_id=goal.employee_id,
        actor_id=current_user.id,
        event_type=EventType.goal_approved,
        payload=payload,
        linked_goal_id=goal.id,
    )

    await db.commit()
    await db.refresh(goal)
    return GoalRead.model_validate(goal)


# ---------------------------------------------------------------------------
# PATCH /goals/{goal_id}/reject — pending_approval → rejected (manager only)
# ---------------------------------------------------------------------------
class RejectBody(BaseModel):
    note: str  # required for rejection


@router.patch("/{goal_id}/reject", response_model=GoalRead)
async def reject_goal(
    goal_id: UUID,
    body: RejectBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GoalRead:
    """
    Transition goal from pending_approval → rejected. Manager-only.
    Appends a goal_rejected timeline event with a required note.
    Requirements: 3.1, 3.4, 3.5, 7.2, 17.2
    """
    goal = await db.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found.",
        )

    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only managers may reject goals.",
        )

    _assert_transition(goal, ModelGoalStatus.rejected)
    goal.status = ModelGoalStatus.rejected

    await append_event(
        db=db,
        employee_id=goal.employee_id,
        actor_id=current_user.id,
        event_type=EventType.goal_rejected,
        payload={
            "goal_id": str(goal.id),
            "title": goal.title,
            "status": goal.status.value,
            "note": body.note,
        },
        linked_goal_id=goal.id,
    )

    await db.commit()
    await db.refresh(goal)
    return GoalRead.model_validate(goal)


# ---------------------------------------------------------------------------
# PATCH /goals/{goal_id}/progress — update progress on an approved goal
# ---------------------------------------------------------------------------
@router.patch("/{goal_id}/progress", response_model=GoalRead)
async def update_progress(
    goal_id: UUID,
    body: GoalProgressUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GoalRead:
    """
    Update progress and health on an approved goal.
    Appends a progress_updated timeline event with before/after diff.
    Requirements: 4.1, 4.2, 4.3, 4.4, 16.2
    """
    goal = await db.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found.",
        )

    if goal.status != ModelGoalStatus.approved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Progress updates are only allowed on approved goals. "
                f"Current status: '{goal.status}'."
            ),
        )

    # Capture before-state — Requirements 4.2
    previous_progress = goal.progress
    previous_health = goal.health.value if hasattr(goal.health, "value") else str(goal.health)

    # Apply update
    goal.progress = body.progress
    goal.health = ModelGoalHealth(body.health.value)

    new_health = goal.health.value if hasattr(goal.health, "value") else str(goal.health)

    event_payload: dict = {
        "goal_id": str(goal.id),
        "previous_progress": previous_progress,
        "new_progress": body.progress,
        "previous_health": previous_health,
        "new_health": new_health,
    }
    if body.note is not None:
        event_payload["note"] = body.note

    await append_event(
        db=db,
        employee_id=goal.employee_id,
        actor_id=current_user.id,
        event_type=EventType.progress_updated,
        payload=event_payload,
        linked_goal_id=goal.id,
    )

    await db.commit()
    await db.refresh(goal)
    return GoalRead.model_validate(goal)
