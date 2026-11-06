from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class KnowledgeDocumentOut(BaseModel):
    id: str
    title: str
    version: str
    owner_id: str
    effective_at: datetime
    source_type: str
    acl: dict[str, Any]
    status: str
    parse_error: str | None = None
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentListResponse(BaseModel):
    items: list[KnowledgeDocumentOut]
    next_cursor: str | None = None


class KnowledgeChunkOut(BaseModel):
    id: str
    doc_id: str
    doc_version: str
    content: str
    page: int
    section: str
    offset_start: int
    offset_end: int
    ordinal: int
    created_at: datetime


class KnowledgeChunkListResponse(BaseModel):
    items: list[KnowledgeChunkOut]
    total: int


class KnowledgeDocumentDetail(KnowledgeDocumentOut):
    chunks: list[KnowledgeChunkOut]


class KnowledgeLocatorOut(BaseModel):
    doc_id: str
    chunk_id: str
    title: str
    version: str
    status: str
    page: int
    section: str
    offset_start: int
    offset_end: int
    quote: str
    raw_content: str


class KnowledgeSearchItem(BaseModel):
    chunk_id: str
    doc_id: str
    title: str
    version: str
    page: int
    section: str
    quote: str
    score: float


class KnowledgeSearchResponse(BaseModel):
    query: str
    items: list[KnowledgeSearchItem]


class KnowledgeDocumentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    version: str | None = Field(default=None, max_length=30)
    status: str | None = None
