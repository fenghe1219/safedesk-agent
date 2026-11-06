from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import new_id
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.schemas.knowledge import KnowledgeChunkOut, KnowledgeDocumentOut
from app.services.chunking import chunk_text
from app.services.retrieval import embed_text


def to_document_out(document: KnowledgeDocument) -> KnowledgeDocumentOut:
    return KnowledgeDocumentOut(
        id=document.id,
        title=document.title,
        version=document.version,
        owner_id=document.owner_id,
        effective_at=document.effective_at,
        source_type=document.source_type,
        acl=document.acl or {},
        status=document.status,
        parse_error=document.parse_error,
        chunk_count=document.chunk_count,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def to_chunk_out(chunk: KnowledgeChunk) -> KnowledgeChunkOut:
    return KnowledgeChunkOut(
        id=chunk.id,
        doc_id=chunk.doc_id,
        doc_version=chunk.doc_version,
        content=chunk.content,
        page=chunk.page,
        section=chunk.section,
        offset_start=chunk.offset_start,
        offset_end=chunk.offset_end,
        ordinal=chunk.ordinal,
        created_at=chunk.created_at,
    )


async def create_document(
    db: AsyncSession,
    *,
    title: str,
    version: str,
    owner_id: str,
    raw_content: str,
    source_type: str,
    acl: dict[str, Any] | None = None,
) -> KnowledgeDocument:
    raw_content = raw_content.replace("\r\n", "\n").replace("\r", "\n")
    document = KnowledgeDocument(
        id=new_id("doc"),
        title=title.strip(),
        version=version.strip() or "v1",
        owner_id=owner_id,
        source_type=source_type,
        file_uri="",
        content_hash=hashlib.sha256(raw_content.encode("utf-8")).hexdigest(),
        acl=acl or {"departments": []},
        status="READY",
        chunk_count=0,
        raw_content=raw_content,
    )
    db.add(document)
    await db.flush()
    await rebuild_chunks(db, document)
    return document


async def rebuild_chunks(db: AsyncSession, document: KnowledgeDocument) -> int:
    await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.doc_id == document.id))
    parsed = chunk_text(document.raw_content)
    for item in parsed:
        db.add(
            KnowledgeChunk(
                id=new_id("chunk"),
                doc_id=document.id,
                doc_version=document.version,
                content=item.content,
                page=item.page,
                section=item.section,
                offset_start=item.offset_start,
                offset_end=item.offset_end,
                ordinal=item.ordinal,
                acl_snapshot=document.acl or {},
                embedding=embed_text(f"{document.title} {item.section} {item.content}"),
                chunk_metadata={"source_type": document.source_type},
            )
        )
    document.chunk_count = len(parsed)
    document.parse_error = None
    await db.flush()
    return len(parsed)


async def get_document(db: AsyncSession, document_id: str) -> KnowledgeDocument | None:
    result = await db.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
    )
    return result.scalar_one_or_none()


async def get_chunk(db: AsyncSession, chunk_id: str) -> KnowledgeChunk | None:
    result = await db.execute(select(KnowledgeChunk).where(KnowledgeChunk.id == chunk_id))
    return result.scalar_one_or_none()
