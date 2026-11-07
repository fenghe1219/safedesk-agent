from datetime import datetime

from pydantic import BaseModel


class MemoryEntryOut(BaseModel):
    id: str
    case_id: str | None = None
    scope: str
    kind: str
    key: str
    value: str
    confidence: float
    source_message_id: str | None = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class MemoryListResponse(BaseModel):
    items: list[MemoryEntryOut]


class MemoryDeleteResponse(BaseModel):
    deleted: bool
    entry_id: str
