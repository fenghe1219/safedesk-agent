from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import as_utc, new_id, utcnow
from app.models.case import Case
from app.models.memory import MemoryEntry
from app.models.message import Message
from app.models.user import User
from app.services.audit import record_event
from app.services.llm import LLMError, chat_completion, get_llm_config, parse_json_object
from app.services.triage import extract_environment, extract_error_message

_REPAIR_HINTS = (
    "还是",
    "仍然",
    "继续",
    "不行",
    "这个",
    "那个",
    "它",
    "同样",
    "还没",
    "现在呢",
    "怎么办",
    "然后呢",
)
_PREFERENCE_PATTERNS = (
    (
        re.compile(r"(?:以后|后续|之后|今后).{0,10}(?:回答|回复).{0,6}(?:详细|完整)"),
        "answer_style",
        "detailed",
        0.95,
    ),
    (
        re.compile(r"(?:以后|后续|之后|今后).{0,10}(?:回答|回复).{0,6}(?:简洁|简短|精简)"),
        "answer_style",
        "concise",
        0.95,
    ),
)


@dataclass(frozen=True)
class QueryRewriteResult:
    query: str
    used_model: bool = False
    fallback_reason: str | None = None
    latency_ms: int = 0
    token_count: int = 0


async def remember_message(
    db: AsyncSession,
    *,
    case: Case,
    user: User,
    message: Message,
    runtime: Any,
    request_id: str,
) -> list[MemoryEntry]:
    if not runtime.memory_enabled or user.id != case.requester_id:
        return []
    candidates: list[tuple[str, str, str, str, float]] = []
    environment = extract_environment(message.content)
    if environment:
        candidates.append(("CASE", "fact", "environment", environment, 0.9))
    error_message = extract_error_message(message.content)
    if error_message:
        candidates.append(("CASE", "fact", "error_message", error_message, 0.85))
    if case.title and case.title not in message.content:
        candidates.append(("CASE", "fact", "case_topic", case.title[:200], 0.8))
    for pattern, key, value, confidence in _PREFERENCE_PATTERNS:
        if pattern.search(message.content):
            candidates.append(("USER", "preference", key, value, confidence))
    if not candidates:
        return []

    entries: list[MemoryEntry] = []
    for scope, kind, key, value, confidence in candidates:
        case_id = case.id if scope == "CASE" else None
        existing = await db.execute(
            select(MemoryEntry)
            .where(
                MemoryEntry.user_id == user.id,
                MemoryEntry.scope == scope,
                MemoryEntry.key == key,
                MemoryEntry.case_id == case_id,
            )
            .order_by(MemoryEntry.updated_at.desc())
            .limit(1)
        )
        entry = existing.scalar_one_or_none()
        if entry is None:
            entry = MemoryEntry(
                id=new_id("mem"),
                user_id=user.id,
                case_id=case_id,
                scope=scope,
                kind=kind,
                key=key,
                value=value,
                confidence=confidence,
                source_message_id=message.id,
                expires_at=(utcnow() + timedelta(days=180)) if scope == "USER" else None,
            )
            db.add(entry)
        else:
            entry.kind = kind
            entry.value = value
            entry.confidence = confidence
            entry.source_message_id = message.id
            entry.updated_at = utcnow()
            if scope == "USER":
                entry.expires_at = utcnow() + timedelta(days=180)
        entries.append(entry)
    await db.flush()
    await record_event(
        db,
        event_type="memory.written",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=case.id,
        payload={
            "entries": [
                {"id": entry.id, "scope": entry.scope, "key": entry.key}
                for entry in entries
            ],
            "policy": "case facts are case-scoped; explicit preferences are user-scoped",
        },
    )
    return entries


async def list_memory_entries(
    db: AsyncSession,
    *,
    user_id: str,
    case_id: str | None = None,
    include_user: bool = True,
) -> list[MemoryEntry]:
    filters = [MemoryEntry.user_id == user_id]
    if not include_user:
        filters.append(MemoryEntry.scope == "CASE")
    if case_id:
        if include_user:
            filters.append(
                or_(MemoryEntry.case_id == case_id, MemoryEntry.scope == "USER")
            )
        else:
            filters.append(MemoryEntry.case_id == case_id)
    now = utcnow()
    result = await db.execute(
        select(MemoryEntry)
        .where(*filters)
        .order_by(MemoryEntry.updated_at.desc(), MemoryEntry.id.desc())
        .limit(100)
    )
    return [
        entry
        for entry in result.scalars().all()
        if entry.expires_at is None or as_utc(entry.expires_at) > now
    ]


async def delete_memory_entry(
    db: AsyncSession,
    *,
    entry_id: str,
    user: User,
    request_id: str,
) -> None:
    entry = await db.get(MemoryEntry, entry_id)
    if entry is None or entry.user_id != user.id:
        raise AppError("NOT_FOUND", "记忆条目不存在", 404)
    await db.delete(entry)
    await record_event(
        db,
        event_type="memory.deleted",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=entry.case_id,
        payload={"entry_id": entry.id, "scope": entry.scope, "key": entry.key},
    )
    await db.commit()


def memory_context(entries: list[MemoryEntry]) -> str:
    if not entries:
        return ""
    labels = {
        "environment": "使用环境",
        "error_message": "已出现报错",
        "case_topic": "Case 主题",
        "answer_style": "回答偏好",
    }
    lines = [
        f"- {labels.get(entry.key, entry.key)}: {entry.value}"
        for entry in entries[:8]
    ]
    return "\n".join(lines)


def needs_query_rewrite(query: str) -> bool:
    if len(query.strip()) <= 18:
        return True
    return any(hint in query for hint in _REPAIR_HINTS)


def local_query_rewrite(
    query: str,
    *,
    case: Case,
    entries: list[MemoryEntry],
) -> str:
    if not needs_query_rewrite(query):
        return query
    values = [case.title]
    values.extend(
        entry.value
        for entry in entries
        if entry.scope == "CASE" and entry.key in {"environment", "error_message", "case_topic"}
    )
    prefix = " ".join(value for value in values if value and value not in query)
    return f"{prefix} {query}".strip() if prefix else query


async def rewrite_query(
    db: AsyncSession,
    *,
    query: str,
    case: Case,
    entries: list[MemoryEntry],
    recent_messages: list[Message],
    runtime: Any,
    request_id: str,
) -> QueryRewriteResult:
    del db, request_id
    started = time.perf_counter()
    if not runtime.query_rewrite_enabled:
        return QueryRewriteResult(query=query)
    config = get_llm_config()
    if not config.enabled or not needs_query_rewrite(query):
        rewritten = local_query_rewrite(query, case=case, entries=entries)
        return QueryRewriteResult(
            query=rewritten,
            latency_ms=max(1, round((time.perf_counter() - started) * 1000)),
        )
    history = "\n".join(
        f"{message.role}: {message.content[:400]}" for message in recent_messages[-6:]
    )
    system = (
        "你是检索查询改写器。把用户当前问题改写成一个独立、可检索的问题。"
        "只补充对话中已明确出现的事实，不得猜测；只输出 JSON："
        '{"query": "改写后的问题"}。'
    )
    user = (
        f"Case 主题：{case.title}\n"
        f"已确认记忆：\n{memory_context(entries) or '无'}\n"
        f"最近对话：\n{history or '无'}\n"
        f"当前问题：{query}"
    )
    try:
        response = await chat_completion(
            config,
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        payload = parse_json_object(response.content)
        rewritten = str(payload.get("query") or "").strip()
        if not rewritten or len(rewritten) > 500:
            raise LLMError("LLM_INVALID_OUTPUT", "查询改写结果为空或过长")
        return QueryRewriteResult(
            query=rewritten,
            used_model=True,
            latency_ms=max(1, round((time.perf_counter() - started) * 1000)),
            token_count=response.usage.total_tokens,
        )
    except LLMError as exc:
        return QueryRewriteResult(
            query=local_query_rewrite(query, case=case, entries=entries),
            fallback_reason=exc.code,
            latency_ms=max(1, round((time.perf_counter() - started) * 1000)),
        )


def memory_payload(entry: MemoryEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "case_id": entry.case_id,
        "scope": entry.scope,
        "kind": entry.kind,
        "key": entry.key,
        "value": entry.value,
        "confidence": entry.confidence,
        "source_message_id": entry.source_message_id,
        "expires_at": entry.expires_at,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    }


def debug_memory_json(entries: list[MemoryEntry]) -> str:
    return json.dumps([memory_payload(entry) for entry in entries], ensure_ascii=False)
