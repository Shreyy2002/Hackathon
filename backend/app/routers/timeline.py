"""
Timeline router — POST and paginated GET for timeline events.
Requirements: 7.2, 7.4, 7.5, 18.3
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.goal import Goal
from app.models.timeline_event import EventType, TimelineEvent
from app.models.user import User
from app.schemas.timeline import TimelineEventCreate, TimelineEventRead
from app.services.timeline_service import append_event
from app.services.websocket_manager import websocket_manager
from app.schemas.timeline import validate_payload

router = APIRouter(prefix="/timeline", tags=["timeline"])


@router.post(
    "/events",
    response_model=TimelineEventRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_timeline_event(
    body: TimelineEventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Append a new timeline event.

    - Validates the payload against the schema for the given event_type (422 on failure).
    - If linked_goal_id is provided, verifies the goal exists and belongs to
      body.employee_id (404 / 403 otherwise).
    - Inserts the event, commits, and broadcasts over WebSocket.
    """
    # 1. Validate payload — raises ValueError → convert to 422
    try:
        validated_payload = validate_payload(body.event_type, body.payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    # 2. Verify linked_goal_id ownership when provided
    if body.linked_goal_id is not None:
        goal = await db.get(Goal, body.linked_goal_id)
        if goal is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Goal {body.linked_goal_id} not found",
            )
        if goal.employee_id != body.employee_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Goal does not belong to the specified employee",
            )

    # 3. Append event (flushes but does NOT commit — we commit below)
    event = await append_event(
        db=db,
        employee_id=body.employee_id,
        actor_id=current_user.id,
        event_type=body.event_type,
        payload=validated_payload,
        linked_goal_id=body.linked_goal_id,
    )

    # 4. Commit and refresh to get server-generated timestamps
    await db.commit()
    await db.refresh(event)

    # 5. Broadcast to WebSocket subscribers for this employee
    event_read = TimelineEventRead.model_validate(event)
    await websocket_manager.broadcast(
        str(body.employee_id),
        event_read.model_dump(mode="json"),
    )

    return event_read


@router.get(
    "/events",
    response_model=List[TimelineEventRead],
)
async def list_timeline_events(
    employee_id: UUID = Query(..., description="UUID of the employee whose timeline to fetch"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Page size (max 100)"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),  # require authentication
):
    """
    Return a paginated, optionally filtered list of timeline events for an
    employee, ordered by created_at DESC.

    Requirements: 7.4 — supports offset/limit pagination and event_type filter.
    """
    stmt = (
        select(TimelineEvent)
        .where(TimelineEvent.employee_id == employee_id)
        .order_by(TimelineEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    if event_type is not None:
        # Validate the event_type string is a known enum member
        try:
            et_enum = EventType(event_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown event_type '{event_type}'",
            )
        stmt = stmt.where(TimelineEvent.event_type == et_enum)

    result = await db.execute(stmt)
    events = result.scalars().all()

    return [TimelineEventRead.model_validate(e) for e in events]
