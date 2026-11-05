from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import new_id
from app.models.audit import AuditEvent


async def record_event(
    db: AsyncSession,
    *,
    event_type: str,
    actor_id: str | None,
    actor_role: str | None,
    request_id: str,
    case_id: str | None = None,
    payload: dict[str, Any] | None = None,
    result: str = "success",
) -> AuditEvent:
    event = AuditEvent(
        id=new_id("audit"),
        case_id=case_id,
        actor_id=actor_id,
        actor_role=actor_role,
        event_type=event_type,
        payload=payload or {},
        request_id=request_id,
        result=result,
    )
    db.add(event)
    return event
