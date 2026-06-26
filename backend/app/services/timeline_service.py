"""
Timeline service — append-only event log operations.
Requirements: 2.1, 2.4, 2.5, 13.1
"""
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.timeline_event import EventType, TimelineEvent


async def append_event(
    db: AsyncSession,
    employee_id: UUID,
    actor_id: UUID,
    event_type: EventType,
    payload: dict,
    linked_goal_id: Optional[UUID] = None,
) -> TimelineEvent:
    """
    Append a new immutable event to the timeline.

    Flushes to the database so the returned event has a valid ``id``, but does
    NOT commit — the caller owns the transaction.  This allows multiple events
    to be written atomically within a single unit of work.

    Preconditions:
    - ``employee_id`` and ``actor_id`` reference existing ``users`` rows.
    - ``event_type`` is a valid ``EventType`` member.
    - ``payload`` is a non-empty dict conforming to the schema for
      ``event_type`` (callers should run ``validate_payload`` first).
    - If ``linked_goal_id`` is provided it references a ``goals`` row owned
      by ``employee_id``.

    Postconditions:
    - A new row is inserted into ``timeline_events``.
    - No existing rows are modified.
    - The returned ``TimelineEvent`` has a valid UUID ``id``.
    - The caller's transaction is NOT yet committed.
    """
    event = TimelineEvent(
        employee_id=employee_id,
        actor_id=actor_id,
        event_type=event_type,
        payload=payload,
        linked_goal_id=linked_goal_id,
    )
    db.add(event)
    await db.flush()  # get ID without committing — caller owns the transaction
    return event
