from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import request_id, require_csrf, require_permission
from app.core.errors import AppError
from app.core.rbac import has_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.ticket import (
    AssigneeListResponse,
    TicketCategory,
    TicketCreate,
    TicketCreateResponse,
    TicketDetailOut,
    TicketListResponse,
    TicketNoteCreate,
    TicketNoteOut,
    TicketOut,
    TicketPriority,
    TicketStatus,
    TicketTransition,
    TicketUpdate,
)
from app.services.case_service import get_accessible_case, to_case_out
from app.services.ticket_service import (
    add_ticket_note,
    confirm_ticket,
    get_accessible_ticket,
    get_draft_for_case,
    list_assignees,
    list_tickets,
    to_ticket_detail,
    to_ticket_out,
    transition_ticket,
    update_ticket,
)

router = APIRouter(prefix="/tickets", tags=["tickets"])
case_router = APIRouter(prefix="/cases", tags=["tickets"])


@router.get("/assignees", response_model=AssigneeListResponse)
async def get_assignees(
    _: User = Depends(require_permission("ticket:view")),
    db: AsyncSession = Depends(get_db),
) -> AssigneeListResponse:
    return AssigneeListResponse(items=await list_assignees(db))


@router.get("", response_model=TicketListResponse)
async def get_tickets(
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None),
    status: TicketStatus | None = Query(default=None),
    category: TicketCategory | None = Query(default=None),
    priority: TicketPriority | None = Query(default=None),
    assignee_id: str | None = Query(default=None, max_length=40),
    q: str | None = Query(default=None, max_length=100),
    user: User = Depends(require_permission("ticket:view")),
    db: AsyncSession = Depends(get_db),
) -> TicketListResponse:
    items, next_cursor = await list_tickets(
        db,
        user=user,
        limit=limit,
        cursor=cursor,
        status=status,
        category=category,
        priority=priority,
        assignee_id=assignee_id,
        query=q,
    )
    return TicketListResponse(items=items, next_cursor=next_cursor)


@router.post("", response_model=TicketCreateResponse, status_code=201)
async def create_ticket(
    payload: TicketCreate,
    request: Request,
    user: User = Depends(require_permission("ticket:manage")),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> TicketCreateResponse:
    case = await get_accessible_case(db, user, payload.case_id)
    if case.status == "CANCELLED":
        raise AppError("INVALID_STATE", "Case 已关闭，无法创建工单", 409)
    ticket = await confirm_ticket(
        db,
        case=case,
        payload=payload,
        user=user,
        request_id=request_id(request),
    )
    await db.commit()
    detail = await to_ticket_detail(db, ticket, include_notes=True)
    return TicketCreateResponse(ticket=detail, case=to_case_out(case).model_dump(mode="json"))


@router.get("/{ticket_id}", response_model=TicketDetailOut)
async def get_ticket(
    ticket_id: str,
    user: User = Depends(require_permission("ticket:view")),
    db: AsyncSession = Depends(get_db),
) -> TicketDetailOut:
    ticket = await get_accessible_ticket(db, user, ticket_id)
    return await to_ticket_detail(
        db,
        ticket,
        include_notes=has_permission(user.role, "ticket:manage"),
    )


@router.patch("/{ticket_id}", response_model=TicketDetailOut)
async def patch_ticket(
    ticket_id: str,
    payload: TicketUpdate,
    request: Request,
    user: User = Depends(require_permission("ticket:manage")),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> TicketDetailOut:
    ticket = await get_accessible_ticket(db, user, ticket_id, for_manage=True)
    await update_ticket(
        db,
        ticket=ticket,
        payload=payload,
        user=user,
        request_id=request_id(request),
    )
    await db.commit()
    return await to_ticket_detail(db, ticket, include_notes=True)


@router.post("/{ticket_id}/transition", response_model=TicketDetailOut)
async def post_transition(
    ticket_id: str,
    payload: TicketTransition,
    request: Request,
    user: User = Depends(require_permission("ticket:manage")),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> TicketDetailOut:
    ticket = await get_accessible_ticket(db, user, ticket_id, for_manage=True)
    await transition_ticket(
        db,
        ticket=ticket,
        payload=payload,
        user=user,
        request_id=request_id(request),
    )
    await db.commit()
    return await to_ticket_detail(db, ticket, include_notes=True)


@router.post("/{ticket_id}/notes", response_model=TicketNoteOut, status_code=201)
async def post_note(
    ticket_id: str,
    payload: TicketNoteCreate,
    request: Request,
    user: User = Depends(require_permission("ticket:manage")),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> TicketNoteOut:
    ticket = await get_accessible_ticket(db, user, ticket_id, for_manage=True)
    note = await add_ticket_note(
        db,
        ticket=ticket,
        payload=payload,
        user=user,
        request_id=request_id(request),
    )
    await db.commit()
    return note


@case_router.get("/{case_id}/ticket-draft", response_model=TicketOut)
async def get_case_ticket_draft(
    case_id: str,
    user: User = Depends(require_permission("ticket:view")),
    db: AsyncSession = Depends(get_db),
) -> TicketOut:
    case = await get_accessible_case(db, user, case_id)
    draft = await get_draft_for_case(db, case.id)
    if draft is None:
        raise AppError("NOT_FOUND", "工单草稿不存在", 404)
    return await to_ticket_out(db, draft)
