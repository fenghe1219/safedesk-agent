from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TicketCategory = Literal[
    "account_permission",
    "network_vpn",
    "software",
    "hardware",
    "email_collaboration",
    "security_incident",
    "other",
]
TicketPriority = Literal["P1", "P2", "P3", "P4"]
TicketStatus = Literal[
    "DRAFT",
    "OPEN",
    "ASSIGNED",
    "IN_PROGRESS",
    "RESOLVED",
    "CLOSED",
    "CANCELLED",
    "REOPENED",
]


class TicketFields(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    category: TicketCategory
    priority: TicketPriority
    priority_reason: str = Field(min_length=1, max_length=300)
    affected_system: str | None = Field(default=None, max_length=120)
    environment: str | None = Field(default=None, max_length=120)
    error_message: str | None = Field(default=None, max_length=1000)
    urgency_reason: str | None = Field(default=None, max_length=300)
    suggested_assignee_id: str | None = Field(default=None, max_length=40)


class TicketFieldsUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    category: TicketCategory | None = None
    priority: TicketPriority | None = None
    priority_reason: str | None = Field(default=None, min_length=1, max_length=300)
    affected_system: str | None = Field(default=None, max_length=120)
    environment: str | None = Field(default=None, max_length=120)
    error_message: str | None = Field(default=None, max_length=1000)
    urgency_reason: str | None = Field(default=None, max_length=300)
    suggested_assignee_id: str | None = Field(default=None, max_length=40)
    assignee_id: str | None = Field(default=None, max_length=40)


class TicketCreate(BaseModel):
    case_id: str
    draft_version: int | None = Field(default=None, ge=1)
    fields: TicketFields


class TicketUpdate(BaseModel):
    version: int = Field(ge=1)
    fields: TicketFieldsUpdate


class TicketTransition(BaseModel):
    version: int = Field(ge=1)
    to_status: TicketStatus
    note: str | None = Field(default=None, max_length=1000)
    assignee_id: str | None = Field(default=None, max_length=40)


class TicketNoteCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class TicketNoteOut(BaseModel):
    id: str
    ticket_id: str
    author_id: str
    author_name: str
    content: str
    created_at: datetime


class TicketOut(BaseModel):
    id: str
    case_id: str
    requester_id: str
    requester_name: str
    title: str
    description: str
    category: str
    category_label: str
    priority: str
    priority_label: str
    priority_reason: str
    affected_system: str | None = None
    environment: str | None = None
    error_message: str | None = None
    urgency_reason: str | None = None
    suggested_assignee_id: str | None = None
    suggested_assignee_name: str | None = None
    suggested_assignee_reason: str | None = None
    assignee_id: str | None = None
    assignee_name: str | None = None
    status: str
    status_label: str
    fields: dict[str, object]
    missing_fields: list[str]
    version: int
    created_at: datetime
    updated_at: datetime


class TicketDetailOut(TicketOut):
    notes: list[TicketNoteOut] = []


class TicketListResponse(BaseModel):
    items: list[TicketOut]
    next_cursor: str | None = None


class TicketCreateResponse(BaseModel):
    ticket: TicketDetailOut
    case: dict[str, object]


class AssigneeOut(BaseModel):
    id: str
    name: str
    email: str
    role: str
    role_label: str
    department: str
    open_ticket_count: int


class AssigneeListResponse(BaseModel):
    items: list[AssigneeOut]
