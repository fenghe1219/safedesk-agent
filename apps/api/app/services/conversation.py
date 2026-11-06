from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import new_id, utcnow
from app.models.case import Case
from app.models.knowledge import KnowledgeDocument
from app.models.message import Citation, Message
from app.models.user import User
from app.schemas.message import CitationOut, MessageOut
from app.services.answer import MODEL_VERSION, PROMPT_VERSION, AnswerPlan, build_answer
from app.services.audit import record_event
from app.services.case_service import CASE_STATUS_LABELS
from app.services.retrieval import retrieve_chunks


@dataclass(frozen=True)
class SSEEvent:
    event: str
    data: dict[str, Any]


@dataclass(frozen=True)
class Exchange:
    user_message: Message
    assistant_message: Message
    plan: AnswerPlan
    citations: list[Citation]
    events: list[SSEEvent]


async def list_case_messages(db: AsyncSession, case_id: str) -> list[MessageOut]:
    result = await db.execute(
        select(Message).where(Message.case_id == case_id).order_by(Message.created_at.asc())
    )
    messages = list(result.scalars().all())
    if not messages:
        return []
    message_ids = [message.id for message in messages]
    citation_result = await db.execute(
        select(Citation)
        .where(Citation.message_id.in_(message_ids))
        .order_by(Citation.message_id, Citation.ordinal)
    )
    citations = list(citation_result.scalars().all())
    document_ids = {citation.doc_id for citation in citations}
    documents: dict[str, KnowledgeDocument] = {}
    if document_ids:
        document_result = await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id.in_(document_ids))
        )
        documents = {document.id: document for document in document_result.scalars().all()}

    by_message: dict[str, list[CitationOut]] = {}
    for citation in citations:
        document = documents.get(citation.doc_id)
        by_message.setdefault(citation.message_id, []).append(
            CitationOut(
                id=citation.id,
                index=citation.ordinal,
                chunk_id=citation.chunk_id,
                doc_id=citation.doc_id,
                title=document.title if document else "来源不可用",
                version=citation.doc_version,
                page=citation.page,
                section=citation.section,
                quote=citation.quote,
                offset_start=citation.offset_start,
                offset_end=citation.offset_end,
                source_available=bool(document and document.status == "READY"),
            )
        )

    return [
        MessageOut(
            id=message.id,
            case_id=message.case_id,
            role=message.role,
            content=message.content,
            status=message.status,
            citations=by_message.get(message.id, []),
            model_version=message.model_version,
            prompt_version=message.prompt_version,
            created_at=message.created_at,
        )
        for message in messages
    ]


async def process_message(
    db: AsyncSession,
    *,
    case: Case,
    user: User,
    content: str,
    request_id: str,
    client_message_id: str | None = None,
) -> Exchange:
    normalized = content.strip()
    user_message = Message(
        id=new_id("msg"),
        case_id=case.id,
        role="user",
        content=normalized,
        status="COMPLETE",
        citations=[],
        request_id=request_id,
        client_message_id=client_message_id,
    )
    db.add(user_message)
    await db.flush()

    await record_event(
        db,
        event_type="message.received",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=case.id,
        payload={"message_id": user_message.id, "length": len(normalized)},
    )

    hits = await retrieve_chunks(db, normalized, user, limit=5)
    plan = build_answer(normalized, hits)
    assistant_message = Message(
        id=new_id("msg"),
        case_id=case.id,
        role="assistant",
        content=plan.content,
        status="COMPLETE",
        citations=[],
        model_version=MODEL_VERSION,
        prompt_version=PROMPT_VERSION,
        request_id=request_id,
    )
    db.add(assistant_message)
    await db.flush()

    citation_rows: list[Citation] = []
    for citation_plan in plan.citations:
        row = Citation(
            id=new_id("cit"),
            message_id=assistant_message.id,
            chunk_id=citation_plan.chunk.id,
            doc_id=citation_plan.document.id,
            doc_version=citation_plan.document.version,
            ordinal=citation_plan.index,
            quote=citation_plan.quote,
            locator={
                "page": citation_plan.chunk.page,
                "section": citation_plan.chunk.section,
                "offset_start": citation_plan.chunk.offset_start,
                "offset_end": citation_plan.chunk.offset_end,
            },
            page=citation_plan.chunk.page,
            section=citation_plan.chunk.section,
            offset_start=citation_plan.chunk.offset_start,
            offset_end=citation_plan.chunk.offset_end,
        )
        db.add(row)
        citation_rows.append(row)
    assistant_message.citations = [row.id for row in citation_rows]

    await record_event(
        db,
        event_type="retrieval.completed",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=case.id,
        payload={
            "query": normalized,
            "evidence_count": len(hits),
            "chunk_ids": [hit.chunk.id for hit in hits],
        },
    )
    await record_event(
        db,
        event_type="answer.refused" if plan.refused else "answer.generated",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=case.id,
        payload={
            "message_id": assistant_message.id,
            "intent": plan.intent,
            "citation_ids": [row.id for row in citation_rows],
        },
    )

    case.status = "REFUSED" if plan.refused else "ANSWERED"
    case.current_node = "refused" if plan.refused else "answer"
    case.intent = plan.intent
    case.updated_at = utcnow()
    await db.commit()

    events = _build_events(assistant_message, plan, citation_rows, request_id, user_message.id)
    return Exchange(
        user_message=user_message,
        assistant_message=assistant_message,
        plan=plan,
        citations=citation_rows,
        events=events,
    )


def _build_events(
    assistant_message: Message,
    plan: AnswerPlan,
    citations: list[Citation],
    request_id: str,
    user_message_id: str,
) -> list[SSEEvent]:
    events: list[SSEEvent] = [
        SSEEvent(
            "step",
            {
                "name": "understand",
                "label": "已理解问题",
                "phase": "intake",
                "status": "complete",
                "message_id": user_message_id,
            },
        ),
        SSEEvent(
            "step",
            {
                "name": "retrieve",
                "label": "正在检索知识库",
                "phase": "retrieval",
                "status": "running",
            },
        ),
        SSEEvent(
            "step",
            {
                "name": "retrieve",
                "label": f"已找到 {plan.evidence_count} 条相关依据",
                "phase": "retrieval",
                "status": "complete",
            },
        ),
    ]

    for citation, chunk in zip(citations, plan.citations, strict=False):
        events.append(
            SSEEvent(
                "citation",
                {
                    "index": citation.ordinal,
                    "citation_id": citation.id,
                    "chunk_id": citation.chunk_id,
                    "doc_id": citation.doc_id,
                    "title": chunk.document.title,
                    "version": citation.doc_version,
                    "page": citation.page,
                    "section": citation.section,
                    "quote": citation.quote,
                    "source_available": True,
                },
            )
        )

    for piece in _stream_pieces(plan.content):
        events.append(SSEEvent("token", {"text": piece}))

    status = "REFUSED" if plan.refused else "ANSWERED"
    phase = "solution"
    events.append(
        SSEEvent(
            "status",
            {
                "case_status": status,
                "status_label": CASE_STATUS_LABELS[status],
                "phase": phase,
            },
        )
    )
    events.append(
        SSEEvent(
            "done",
            {
                "case_status": status,
                "message_id": assistant_message.id,
                "request_id": request_id,
                "refused": plan.refused,
                "evidence_count": plan.evidence_count,
            },
        )
    )
    return events


def _stream_pieces(content: str, size: int = 18) -> list[str]:
    pieces: list[str] = []
    cursor = 0
    while cursor < len(content):
        end = min(cursor + size, len(content))
        if end < len(content):
            boundary = max(
                content.rfind("\n", cursor, end),
                content.rfind("。", cursor, end),
                content.rfind("，", cursor, end),
            )
            if boundary > cursor + 5:
                end = boundary + 1
        pieces.append(content[cursor:end])
        cursor = end
    return pieces


def encode_sse(events: list[SSEEvent]) -> str:
    import json

    return "".join(
        f"id: {index}\nevent: {event.event}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"
        for index, event in enumerate(events, start=1)
    )
