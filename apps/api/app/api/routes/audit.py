from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.audit import AuditEventListResponse
from app.services.audit_query import list_audit_events

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events", response_model=AuditEventListResponse)
async def audit_events(
    case_id: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    result: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    _: User = Depends(require_permission("audit:view")),
    db: AsyncSession = Depends(get_db),
) -> AuditEventListResponse:
    return await list_audit_events(
        db,
        case_id=case_id,
        actor_id=actor_id,
        event_type=event_type,
        result=result,
        query=q,
        start_at=start_at,
        end_at=end_at,
        offset=offset,
        limit=limit,
    )
