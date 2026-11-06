from datetime import datetime

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    client_message_id: str | None = Field(default=None, max_length=80)


class CitationOut(BaseModel):
    id: str
    index: int
    chunk_id: str
    doc_id: str
    title: str
    version: str
    page: int
    section: str
    quote: str
    offset_start: int
    offset_end: int
    source_available: bool


class MessageOut(BaseModel):
    id: str
    case_id: str
    role: str
    content: str
    status: str
    citations: list[CitationOut] = []
    model_version: str = ""
    prompt_version: str = ""
    created_at: datetime


class MessageListResponse(BaseModel):
    items: list[MessageOut]
    next_cursor: str | None = None
