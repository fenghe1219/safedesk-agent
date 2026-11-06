from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEventOut(BaseModel):
    id: str
    case_id: str | None = None
    actor_id: str | None = None
    actor_name: str | None = None
    actor_role: str | None = None
    event_type: str
    summary: str
    payload: dict[str, Any]
    request_id: str
    result: str
    created_at: datetime


class AuditEventListResponse(BaseModel):
    items: list[AuditEventOut]
    total: int
    offset: int
    limit: int
    event_types: list[str]
