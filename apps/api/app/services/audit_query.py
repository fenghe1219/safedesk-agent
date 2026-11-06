from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.user import User
from app.schemas.audit import AuditEventListResponse, AuditEventOut
from app.services.case_service import EVENT_SUMMARIES

_SENSITIVE_KEY_PARTS = (
    "password",
    "passwd",
    "token",
    "secret",
    "cookie",
    "authorization",
    "credential",
    "api_key",
    "private_key",
)


def safe_payload(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return "[已截断]"
    if isinstance(value, dict):
        projected: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in _SENSITIVE_KEY_PARTS):
                projected[str(key)] = "[已脱敏]"
            else:
                projected[str(key)] = safe_payload(item, depth=depth + 1)
        return projected
    if isinstance(value, list):
        return [safe_payload(item, depth=depth + 1) for item in value[:50]]
    if isinstance(value, str):
        return value if len(value) <= 500 else f"{value[:500]}…"
    return value


def _to_out(event: AuditEvent, actor_name: str | None) -> AuditEventOut:
    return AuditEventOut(
        id=event.id,
        case_id=event.case_id,
        actor_id=event.actor_id,
        actor_name=actor_name,
        actor_role=event.actor_role,
        event_type=event.event_type,
        summary=EVENT_SUMMARIES.get(event.event_type, event.event_type),
        payload=safe_payload(dict(event.payload or {})),
        request_id=event.request_id,
        result=event.result,
        created_at=event.created_at,
    )


async def list_audit_events(
    db: AsyncSession,
    *,
    case_id: str | None = None,
    actor_id: str | None = None,
    event_type: str | None = None,
    result: str | None = None,
    query: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    offset: int = 0,
    limit: int = 50,
) -> AuditEventListResponse:
    statement = select(AuditEvent).order_by(AuditEvent.created_at.desc())
    if case_id:
        statement = statement.where(AuditEvent.case_id == case_id)
    if actor_id:
        statement = statement.where(AuditEvent.actor_id == actor_id)
    if event_type:
        statement = statement.where(AuditEvent.event_type == event_type)
    if result:
        statement = statement.where(AuditEvent.result == result)
    if start_at:
        statement = statement.where(AuditEvent.created_at >= start_at)
    if end_at:
        statement = statement.where(AuditEvent.created_at <= end_at)
    events = list((await db.execute(statement)).scalars().all())

    needle = query.strip().lower() if query else ""
    if needle:
        events = [
            event
            for event in events
            if needle
            in " ".join(
                [
                    event.id,
                    event.event_type,
                    event.case_id or "",
                    event.actor_id or "",
                    event.request_id,
                    json.dumps(event.payload or {}, ensure_ascii=False),
                ]
            ).lower()
        ]
    total = len(events)
    page = events[offset : offset + limit]
    actor_ids = {event.actor_id for event in page if event.actor_id}
    names: dict[str, str] = {}
    if actor_ids:
        users = await db.execute(select(User).where(User.id.in_(actor_ids)))
        names = {user.id: user.name for user in users.scalars().all()}
    available_types = sorted({event.event_type for event in events})
    return AuditEventListResponse(
        items=[_to_out(event, names.get(event.actor_id or "")) for event in page],
        total=total,
        offset=offset,
        limit=limit,
        event_types=available_types,
    )
