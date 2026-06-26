"""
Pydantic v2 schemas for the Timeline context.
Requirements: 2.1, 2.4, 2.5
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# EventType enum — mirrors the ORM EventType in models/timeline_event.py
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# JSONB payload validators — one model per event_type
# ---------------------------------------------------------------------------

class GoalEventPayload(BaseModel):
    """Used for: goal_created, goal_submitted, goal_approved, goal_rejected."""
    goal_id: str
    title: str
    status: str
    note: Optional[str] = None


class ProgressEventPayload(BaseModel):
    """Used for: progress_updated."""
    goal_id: str
    previous_progress: int = Field(..., ge=0, le=100)
    new_progress: int = Field(..., ge=0, le=100)
    previous_health: str
    new_health: str
    note: Optional[str] = None


class FeedbackPayload(BaseModel):
    """Used for: feedback, peer_review."""
    text: str = Field(..., min_length=1)
    is_anonymous: bool
    from_user_id: Optional[str] = None
    sentiment_score: Optional[float] = None


class AchievementPayload(BaseModel):
    """Used for: achievement."""
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    linked_goal_id: Optional[str] = None


class CheckInPayload(BaseModel):
    """Used for: check_in."""
    meeting_date: str  # ISO date string, e.g. "2024-01-15"
    notes: str = Field(..., min_length=1)
    action_items: List[str]


class EvidenceTaggedPayload(BaseModel):
    """Used for: evidence_tagged."""
    source_event_id: str
    goal_id: str
    tagged_by: str


# ---------------------------------------------------------------------------
# Payload dispatcher
# ---------------------------------------------------------------------------

_PAYLOAD_MAP = {
    EventType.goal_created: GoalEventPayload,
    EventType.goal_submitted: GoalEventPayload,
    EventType.goal_approved: GoalEventPayload,
    EventType.goal_rejected: GoalEventPayload,
    EventType.progress_updated: ProgressEventPayload,
    EventType.feedback: FeedbackPayload,
    EventType.achievement: AchievementPayload,
    EventType.check_in: CheckInPayload,
    EventType.peer_review: FeedbackPayload,
    EventType.evidence_tagged: EvidenceTaggedPayload,
}


def validate_payload(event_type: EventType, payload_dict: dict) -> dict:
    """
    Validate *payload_dict* against the schema for *event_type*.

    Returns the validated data as a plain dict (always JSON-serialisable for
    JSONB storage).  Raises ``ValueError`` with a descriptive message if
    validation fails.
    """
    model_cls = _PAYLOAD_MAP.get(event_type)
    if model_cls is None:
        raise ValueError(f"No payload schema registered for event_type '{event_type}'")

    try:
        validated = model_cls.model_validate(payload_dict)
    except Exception as exc:
        raise ValueError(
            f"Invalid payload for event_type '{event_type}': {exc}"
        ) from exc

    return validated.model_dump()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class TimelineEventCreate(BaseModel):
    """
    Request body for POST /api/timeline/events.

    Note: actor_id is intentionally absent — it is injected from the
    authenticated ``current_user`` dependency, never trusted from the client.
    """
    employee_id: UUID
    event_type: EventType
    payload: dict
    linked_goal_id: Optional[UUID] = None


class TimelineEventRead(BaseModel):
    """Response schema for a single timeline event."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    actor_id: UUID
    event_type: EventType
    payload: dict
    linked_goal_id: Optional[UUID]
    created_at: datetime
    is_evidence: bool
