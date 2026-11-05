from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import request_id, require_csrf, require_permission
from app.core.errors import AppError
from app.core.rbac import has_permission
from app.core.security import new_id
from app.db.session import get_db
from app.models.audit import AuditEvent
from app.models.case import Case
from app.models.user import User
from app.schemas.case import CaseCreate, CaseListResponse, CaseOut, TimelineResponse
from app.services.audit import record_event
from app.services.case_service import to_case_out, to_timeline_event

router = APIRouter(prefix="/cases", tags=["cases"])


async def _get_accessible_case(db: AsyncSession, user: User, case_id: str) -> Case:
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if case is None:
        raise AppError("NOT_FOUND", "Case 不存在", 404)
    if case.requester_id != user.id and not has_permission(user.role, "case:read_all"):
        raise AppError("NOT_FOUND", "Case 不存在", 404)
    return case


@router.get("", response_model=CaseListResponse)
async def list_cases(
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(require_permission("case:read")),
    db: AsyncSession = Depends(get_db),
) -> CaseListResponse:
    statement = select(Case)
    if not has_permission(user.role, "case:read_all"):
        statement = statement.where(Case.requester_id == user.id)
    statement = statement.order_by(Case.updated_at.desc()).limit(limit)
    result = await db.execute(statement)
    cases = result.scalars().all()
    return CaseListResponse(items=[to_case_out(case) for case in cases])


@router.post("", response_model=CaseOut, status_code=201)
async def create_case(
    payload: CaseCreate,
    request: Request,
    user: User = Depends(require_permission("case:create")),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> CaseOut:
    title = payload.title.strip()
    if not title:
        raise AppError("VALIDATION_ERROR", "问题标题不能为空", 422)

    case = Case(
        id=new_id("case"),
        title=title,
        requester_id=user.id,
        status="NEW",
        current_node="intake",
    )
    db.add(case)
    await record_event(
        db,
        event_type="case.created",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id(request),
        case_id=case.id,
        payload={"title": title, "status": case.status},
    )
    await db.commit()
    return to_case_out(case)


@router.get("/{case_id}", response_model=CaseOut)
async def get_case(
    case_id: str,
    user: User = Depends(require_permission("case:read")),
    db: AsyncSession = Depends(get_db),
) -> CaseOut:
    case = await _get_accessible_case(db, user, case_id)
    return to_case_out(case)


@router.get("/{case_id}/timeline", response_model=TimelineResponse)
async def get_case_timeline(
    case_id: str,
    user: User = Depends(require_permission("case:read")),
    db: AsyncSession = Depends(get_db),
) -> TimelineResponse:
    await _get_accessible_case(db, user, case_id)
    result = await db.execute(
        select(AuditEvent)
        .where(AuditEvent.case_id == case_id)
        .order_by(AuditEvent.created_at.asc())
    )
    events = result.scalars().all()
    return TimelineResponse(items=[to_timeline_event(event) for event in events])
