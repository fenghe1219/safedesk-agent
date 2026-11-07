from __future__ import annotations

import time
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
from app.services.action_service import (
    action_intent_from_proposal,
    create_action_proposal,
    detect_action_intent,
    get_active_action_for_case,
    to_action_out,
    to_approval_out,
)
from app.services.admin_settings import get_active_prompt, get_runtime_config
from app.services.agent import plan_from_agent_result, run_agent
from app.services.answer import (
    MODEL_VERSION,
    PROMPT_VERSION,
    AnswerPlan,
    build_answer,
    sensitive_refusal,
)
from app.services.audit import record_event
from app.services.case_service import CASE_PHASES, CASE_STATUS_LABELS, to_case_out
from app.services.llm import get_llm_config
from app.services.memory import (
    list_memory_entries,
    memory_context,
    remember_message,
    rewrite_query,
)
from app.services.retrieval import retrieve_chunks
from app.services.ticket_service import (
    ticket_draft_payload,
    to_ticket_out,
    upsert_ticket_draft,
)
from app.services.tools import call_read_tool
from app.services.triage import (
    asks_for_ticket,
    build_followup_prompt,
    build_triage,
    classify_category,
    extract_environment,
    extract_error_message,
    looks_like_it_issue,
)


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

    runtime = await get_runtime_config(db)
    memory_entries = []
    if runtime.memory_enabled:
        await remember_message(
            db,
            case=case,
            user=user,
            message=user_message,
            runtime=runtime,
            request_id=request_id,
        )
        memory_entries = await list_memory_entries(db, user_id=user.id, case_id=case.id)
    recent_messages = await _recent_messages(db, case.id, exclude_id=user_message.id)
    rewrite = await rewrite_query(
        db,
        query=normalized,
        case=case,
        entries=memory_entries,
        recent_messages=recent_messages,
        runtime=runtime,
        request_id=request_id,
    )
    resolved_query = rewrite.query
    if rewrite.used_model or resolved_query != normalized:
        await record_event(
            db,
            event_type="query.rewritten",
            actor_id=user.id,
            actor_role=user.role,
            request_id=request_id,
            case_id=case.id,
            payload={
                "original": normalized,
                "rewritten": resolved_query,
                "used_model": rewrite.used_model,
                "fallback_reason": rewrite.fallback_reason,
                "memory_entries": len(memory_entries),
                "latency_ms": rewrite.latency_ms,
                "token_count": rewrite.token_count,
            },
        )
    retrieval_started = time.perf_counter()
    hits = await retrieve_chunks(
        db,
        resolved_query,
        user,
        limit=runtime.retrieval_limit,
        min_score=runtime.retrieval_min_score,
    )
    retrieval_latency_ms = max(1, round((time.perf_counter() - retrieval_started) * 1000))
    active_prompt = await get_active_prompt(db)
    answer_started = time.perf_counter()
    agent_result = None
    plan = None
    use_agent = runtime.answer_mode in {"auto", "model"} and get_llm_config().enabled
    if use_agent:
        agent_result = await run_agent(
            db,
            case=case,
            user=user,
            query=resolved_query,
            hits=hits,
            prompt=active_prompt,
            runtime=runtime,
            recent_messages=recent_messages,
            memory_text=memory_context(memory_entries),
            request_id=request_id,
        )
        if agent_result is not None:
            plan = plan_from_agent_result(
                query=resolved_query,
                hits=hits,
                result=agent_result,
                max_citations=runtime.max_context_chunks,
            )
    if plan is None:
        plan = build_answer(
            resolved_query,
            hits,
            max_citations=runtime.max_context_chunks,
            style=runtime.answer_style,
        )
    if use_agent and (agent_result is None or agent_result.fallback_reason):
        await record_event(
            db,
            event_type="agent.fallback",
            actor_id=user.id,
            actor_role=user.role,
            request_id=request_id,
            case_id=case.id,
            payload={
                "reason": (
                    agent_result.fallback_reason
                    if agent_result is not None
                    else "provider_unavailable"
                ),
                "provider": get_llm_config().provider,
                "model": get_llm_config().model,
            },
            result="fallback",
        )
    answer_latency_ms = max(1, round((time.perf_counter() - answer_started) * 1000))
    action = None
    approval = None
    diagnostic = None
    if user.id == case.requester_id and sensitive_refusal(normalized) is None:
        intent = None
        if agent_result is not None and agent_result.write_proposal is not None:
            intent = action_intent_from_proposal(
                tool_name=agent_result.write_proposal.name,
                args=agent_result.write_proposal.arguments,
                case=case,
                content=normalized,
            )
        elif agent_result is None or agent_result.fallback_reason is not None:
            intent = detect_action_intent(normalized, case)
        if intent is not None:
            diagnostic = await call_read_tool(
                db,
                tool_name=intent.diagnostic_tool,
                raw_args=intent.diagnostic_args,
                user=user,
                case=case,
                request_id=request_id,
            )
            action, approval = await create_action_proposal(
                db,
                case=case,
                user=user,
                intent=intent,
                diagnostic=diagnostic,
                evidence_ids=[
                    f"chunk:{item.chunk.id}" for item in plan.citations
                ],
                request_id=request_id,
            )
    active_action = (
        action
        if action is not None
        else await get_active_action_for_case(db, case.id)
    )
    triage_draft = None
    ticket = None
    triage_missing = False
    if action is not None:
        action_parts = [diagnostic.summary if diagnostic else "已完成只读诊断。"]
        if plan.content and not plan.refused:
            action_parts.append(plan.content)
        action_parts.append(
            f"已生成「{action.tool_label}」动作建议（审批号 {approval.id}）。"
            "影响对象、参数和有效期已经固定，必须由审批人确认后才会执行；"
            "审批前不会调用写工具。"
        )
        effective_plan = AnswerPlan(
            content="\n\n".join(action_parts),
            citations=plan.citations,
            refused=False,
            intent="action_approval",
            evidence_count=len(plan.citations),
        )
    elif active_action is None and _should_attempt_triage(
        case=case, content=normalized, plan=plan
    ):
        triage_draft = build_triage(await _case_user_texts(db, case.id))
        if triage_draft.missing_fields:
            triage_missing = True
            effective_plan = AnswerPlan(
                content=build_followup_prompt(triage_draft),
                citations=[],
                refused=False,
                intent="ticket_triage",
                evidence_count=0,
            )
        else:
            ticket = await upsert_ticket_draft(
                db,
                case=case,
                triage=triage_draft,
                user=user,
                request_id=request_id,
            )
            citation_plans = [] if plan.refused else plan.citations
            content_parts: list[str] = []
            if not plan.refused:
                content_parts.append(plan.content)
            content_parts.append(
                "已整理成工单草稿，请核对分类、优先级、处理人建议和字段；"
                "确认前不会创建工单。"
            )
            effective_plan = AnswerPlan(
                content="\n\n".join(content_parts),
                citations=citation_plans,
                refused=False,
                intent="ticket_triage",
                evidence_count=len(citation_plans),
            )
    else:
        effective_plan = plan

    assistant_message = Message(
        id=new_id("msg"),
        case_id=case.id,
        role="assistant",
        content=effective_plan.content,
        status="COMPLETE",
        citations=[],
        model_version=(
            agent_result.model
            if agent_result is not None
            and agent_result.used_model
            and not agent_result.fallback_reason
            else MODEL_VERSION
        ),
        prompt_version=active_prompt.version or PROMPT_VERSION,
        request_id=request_id,
    )
    db.add(assistant_message)
    await db.flush()

    citation_rows: list[Citation] = []
    for citation_plan in effective_plan.citations:
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
            "query": resolved_query,
            "original_query": normalized,
            "query_rewritten": resolved_query != normalized,
            "evidence_count": len(hits),
            "chunk_ids": [hit.chunk.id for hit in hits],
            "latency_ms": retrieval_latency_ms,
            "retrieval_limit": runtime.retrieval_limit,
            "retrieval_min_score": runtime.retrieval_min_score,
            "max_context_chunks": runtime.max_context_chunks,
            "memory_entries": len(memory_entries),
            "estimated": True,
        },
    )
    if agent_result is not None and agent_result.usage.total_tokens:
        answer_tokens = agent_result.usage.total_tokens
        answer_cost_usd = agent_result.usage.cost_usd
        usage_estimated = agent_result.usage.estimated
    else:
        answer_tokens = max(1, len(effective_plan.content) // 2)
        answer_cost_usd = round(answer_tokens * 0.0000006, 8)
        usage_estimated = True
    if agent_result is not None:
        await record_event(
            db,
            event_type="agent.completed",
            actor_id=user.id,
            actor_role=user.role,
            request_id=request_id,
            case_id=case.id,
            payload={
                "provider": get_llm_config().provider,
                "model": agent_result.model,
                "prompt_version": active_prompt.version,
                "used_model": agent_result.used_model,
                "steps": agent_result.steps,
                "read_observations": len(agent_result.read_observations),
                "write_proposed": (
                    agent_result.write_proposal.name
                    if agent_result.write_proposal is not None
                    else None
                ),
                "fallback_reason": agent_result.fallback_reason,
                "latency_ms": agent_result.latency_ms,
                "token_count": agent_result.usage.total_tokens,
                "cost_usd": agent_result.usage.cost_usd,
                "trace": agent_result.trace,
            },
            result="fallback" if agent_result.fallback_reason else "success",
        )
    await record_event(
        db,
        event_type="answer.refused" if effective_plan.refused else "answer.generated",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=case.id,
        payload={
            "message_id": assistant_message.id,
            "intent": effective_plan.intent,
            "citation_ids": [row.id for row in citation_rows],
            "latency_ms": answer_latency_ms,
            "token_count": answer_tokens,
            "cost_usd": answer_cost_usd,
            "estimated": usage_estimated,
            "agent_used": bool(agent_result and agent_result.used_model),
            "agent_steps": agent_result.steps if agent_result else 0,
            "fallback_reason": agent_result.fallback_reason if agent_result else None,
        },
    )

    if triage_draft is not None:
        if triage_missing:
            case.status = "NEEDS_INPUT"
            case.current_node = "ticket_triage"
    elif active_action is not None:
        case.current_node = case.current_node or "await_approval"
    else:
        case.status = "REFUSED" if effective_plan.refused else "ANSWERED"
        case.current_node = "refused" if effective_plan.refused else "answer"
    if active_action is None:
        case.intent = effective_plan.intent
    case.updated_at = utcnow()
    await db.commit()

    ticket_event = ticket_draft_payload(await to_ticket_out(db, ticket)) if ticket else None
    action_event = None
    if action is not None and approval is not None:
        action_event = {
            "action": (await to_action_out(db, action)).model_dump(mode="json"),
            "approval": (await to_approval_out(db, approval)).model_dump(mode="json"),
            "case": to_case_out(case).model_dump(mode="json"),
        }
    events = _build_events(
        assistant_message,
        effective_plan,
        citation_rows,
        request_id,
        user_message.id,
        case_status=case.status,
        phase=CASE_PHASES.get(case.status, "solution"),
        ticket_event=ticket_event,
        triage=triage_draft is not None,
        action_event=action_event,
    )
    return Exchange(
        user_message=user_message,
        assistant_message=assistant_message,
        plan=effective_plan,
        citations=citation_rows,
        events=events,
    )


def _build_events(
    assistant_message: Message,
    plan: AnswerPlan,
    citations: list[Citation],
    request_id: str,
    user_message_id: str,
    *,
    case_status: str,
    phase: str,
    ticket_event: dict[str, Any] | None,
    triage: bool,
    action_event: dict[str, Any] | None,
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

    if triage:
        events.append(
            SSEEvent(
                "step",
                {
                    "name": "triage",
                    "label": "已完成工单分诊",
                    "phase": phase,
                    "status": "complete",
                },
            )
        )

    if action_event is not None:
        events.append(
            SSEEvent(
                "step",
                {
                    "name": "diagnose",
                    "label": "已执行只读诊断工具",
                    "phase": phase,
                    "status": "complete",
                },
            )
        )
        events.append(
            SSEEvent(
                "step",
                {
                    "name": "approval",
                    "label": "已生成动作建议，等待人工审批",
                    "phase": phase,
                    "status": "complete",
                },
            )
        )

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

    if ticket_event is not None:
        events.append(SSEEvent("ticket_draft", ticket_event))
    if action_event is not None:
        events.append(SSEEvent("action", action_event))

    events.append(
        SSEEvent(
            "status",
            {
                "case_status": case_status,
                "status_label": CASE_STATUS_LABELS.get(case_status, case_status),
                "phase": phase,
            },
        )
    )
    done_payload: dict[str, Any] = {
        "case_status": case_status,
        "message_id": assistant_message.id,
        "request_id": request_id,
        "refused": plan.refused,
        "evidence_count": plan.evidence_count,
    }
    if ticket_event is not None:
        done_payload["ticket_id"] = ticket_event["ticket_id"]
    if action_event is not None:
        done_payload["action_id"] = action_event["action"]["id"]
    events.append(
        SSEEvent(
            "done",
            done_payload,
        )
    )
    return events


async def _case_user_texts(db: AsyncSession, case_id: str) -> list[str]:
    result = await db.execute(
        select(Message.content)
        .where(Message.case_id == case_id, Message.role == "user")
        .order_by(Message.created_at.asc())
    )
    return list(result.scalars().all())


async def _recent_messages(
    db: AsyncSession, case_id: str, *, exclude_id: str | None = None
) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.case_id == case_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(10)
    )
    messages = [message for message in result.scalars().all() if message.id != exclude_id]
    messages.reverse()
    return messages


def _should_attempt_triage(*, case: Case, content: str, plan: AnswerPlan) -> bool:
    if case.ticket_id is not None:
        return False
    if sensitive_refusal(content) is not None:
        return False
    if case.intent == "ticket_triage":
        return True
    if asks_for_ticket(content):
        return True
    if not looks_like_it_issue(content):
        return False
    if _is_question_style(content) and not plan.refused:
        return False
    category, _ = classify_category(content)
    environment = extract_environment(content)
    error_message = extract_error_message(content)
    if plan.refused:
        return True
    return (
        category in {"hardware", "software", "account_permission", "email_collaboration"}
        and environment is None
        and error_message is None
    )


def _is_question_style(content: str) -> bool:
    return any(
        hint in content
        for hint in (
            "怎么",
            "如何",
            "怎么办",
            "怎样",
            "为什么",
            "什么原因",
            "能否",
            "是否",
            "可以吗",
        )
    )


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
