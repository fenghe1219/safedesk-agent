from datetime import datetime

from pydantic import BaseModel, Field


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=80)


class CaseOut(BaseModel):
    id: str
    title: str
    status: str
    status_label: str
    phase: str
    requester_id: str
    current_node: str
    intent: str | None = None
    ticket_id: str | None = None
    action_id: str | None = None
    created_at: datetime
    updated_at: datetime


class CaseListResponse(BaseModel):
    items: list[CaseOut]
    next_cursor: str | None = None


class TimelineEventOut(BaseModel):
    id: str
    event_type: str
    summary: str
    actor_id: str | None = None
    actor_role: str | None = None
    result: str
    created_at: datetime


class TimelineResponse(BaseModel):
    items: list[TimelineEventOut]
