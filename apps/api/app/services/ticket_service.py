from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.rbac import ROLE_LABELS, Role, has_permission
from app.core.security import new_id, utcnow
from app.models.case import Case
from app.models.ticket import Ticket, TicketNote
from app.models.user import User
from app.schemas.ticket import (
    AssigneeOut,
    TicketCreate,
    TicketDetailOut,
    TicketNoteCreate,
    TicketNoteOut,
    TicketOut,
    TicketTransition,
    TicketUpdate,
)
from app.services.audit import record_event
from app.services.triage import (
    CATEGORY_LABELS,
    PRIORITY_LABELS,
    TriageDraft,
    recommend_assignee,
)

STATUS_LABELS: dict[str, str] = {
    "DRAFT": "草稿",
    "OPEN": "待处理",
    "ASSIGNED": "已分派",
    "IN_PROGRESS": "处理中",
    "RESOLVED": "已解决",
    "CLOSED": "已关闭",
    "CANCELLED": "已取消",
    "REOPENED": "已重新打开",
}

TICKET_TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"OPEN", "CANCELLED"}),
    "OPEN": frozenset({"ASSIGNED", "CANCELLED"}),
    "ASSIGNED": frozenset({"IN_PROGRESS", "CANCELLED"}),
    "IN_PROGRESS": frozenset({"RESOLVED", "CANCELLED"}),
    "RESOLVED": frozenset({"CLOSED", "REOPENED"}),
    "CLOSED": frozenset({"REOPENED"}),
    "REOPENED": frozenset({"ASSIGNED", "IN_PROGRESS"}),
    "CANCELLED": frozenset(),
}

ACTIVE_STATUSES = ("OPEN", "ASSIGNED", "IN_PROGRESS", "REOPENED")
FIELD_COLUMNS = (
    "title",
    "description",
    "category",
    "priority",
    "priority_reason",
    "affected_system",
    "environment",
    "error_message",
    "urgency_reason",
)
USER_REFERENCE_ROLES = (Role.SUPPORT.value, Role.ADMIN.value)

SENSITIVE_NOTE_ROLES = frozenset()


def ticket_status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def ticket_category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, category)


def ticket_priority_label(priority: str) -> str:
    return PRIORITY_LABELS.get(priority, priority)


def require_ticket_manage(user: User) -> None:
    if not has_permission(user.role, "ticket:manage"):
        raise AppError("FORBIDDEN", "当前角色没有管理工单的权限", 403)


async def get_accessible_ticket(
    db: AsyncSession,
    user: User,
    ticket_id: str,
    *,
    for_manage: bool = False,
) -> Ticket:
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise AppError("NOT_FOUND", "工单不存在", 404)
    if for_manage:
        require_ticket_manage(user)
        return ticket
    if has_permission(user.role, "ticket:manage") or user.role == Role.APPROVER.value:
        return ticket
    requester_id = await _requester_id(db, ticket.case_id)
    if requester_id != user.id:
        raise AppError("NOT_FOUND", "工单不存在", 404)
    return ticket


async def _requester_id(db: AsyncSession, case_id: str) -> str | None:
    result = await db.execute(select(Case.requester_id).where(Case.id == case_id))
    return result.scalar_one_or_none()


async def _names_for_ids(db: AsyncSession, user_ids: set[str]) -> dict[str, str]:
    if not user_ids:
        return {}
    result = await db.execute(select(User.id, User.name).where(User.id.in_(user_ids)))
    return {user_id: name for user_id, name in result.all()}


async def to_ticket_out(db: AsyncSession, ticket: Ticket) -> TicketOut:
    tickets = await to_ticket_outs(db, [ticket])
    return tickets[0]


async def to_ticket_outs(db: AsyncSession, tickets: list[Ticket]) -> list[TicketOut]:
    if not tickets:
        return []
    case_ids = {ticket.case_id for ticket in tickets}
    requester_result = await db.execute(
        select(Case.id, Case.requester_id).where(Case.id.in_(case_ids))
    )
    requester_by_case = dict(requester_result.all())
    user_ids: set[str] = set(requester_by_case.values())
    for ticket in tickets:
        if ticket.suggested_assignee_id:
            user_ids.add(ticket.suggested_assignee_id)
        if ticket.assignee_id:
            user_ids.add(ticket.assignee_id)
    names = await _names_for_ids(db, user_ids)
    items: list[TicketOut] = []
    for ticket in tickets:
        requester_id = requester_by_case.get(ticket.case_id, "")
        items.append(
            TicketOut(
                id=ticket.id,
                case_id=ticket.case_id,
                requester_id=requester_id,
                requester_name=names.get(requester_id, ""),
                title=ticket.title,
                description=ticket.description,
                category=ticket.category,
                category_label=ticket_category_label(ticket.category),
                priority=ticket.priority,
                priority_label=ticket_priority_label(ticket.priority),
                priority_reason=ticket.priority_reason,
                affected_system=ticket.affected_system,
                environment=ticket.environment,
                error_message=ticket.error_message,
                urgency_reason=ticket.urgency_reason,
                suggested_assignee_id=ticket.suggested_assignee_id,
                suggested_assignee_name=names.get(ticket.suggested_assignee_id or ""),
                suggested_assignee_reason=ticket.suggested_assignee_reason,
                assignee_id=ticket.assignee_id,
                assignee_name=names.get(ticket.assignee_id or ""),
                status=ticket.status,
                status_label=ticket_status_label(ticket.status),
                fields=dict(ticket.fields or {}),
                missing_fields=list(ticket.missing_fields or []),
                version=ticket.version,
                created_at=ticket.created_at,
                updated_at=ticket.updated_at,
            )
        )
    return items


async def to_ticket_detail(
    db: AsyncSession, ticket: Ticket, *, include_notes: bool
) -> TicketDetailOut:
    base = await to_ticket_out(db, ticket)
    notes = await list_ticket_notes(db, ticket.id) if include_notes else []
    return TicketDetailOut(**base.model_dump(), notes=notes)


async def list_ticket_notes(db: AsyncSession, ticket_id: str) -> list[TicketNoteOut]:
    result = await db.execute(
        select(TicketNote)
        .where(TicketNote.ticket_id == ticket_id)
        .order_by(TicketNote.created_at.asc())
    )
    notes = list(result.scalars().all())
    names = await _names_for_ids(db, {note.author_id for note in notes})
    return [
        TicketNoteOut(
            id=note.id,
            ticket_id=note.ticket_id,
            author_id=note.author_id,
            author_name=names.get(note.author_id, ""),
            content=note.content,
            created_at=note.created_at,
        )
        for note in notes
    ]


async def get_draft_for_case(db: AsyncSession, case_id: str) -> Ticket | None:
    result = await db.execute(
        select(Ticket).where(Ticket.case_id == case_id, Ticket.status == "DRAFT")
    )
    return result.scalar_one_or_none()


async def upsert_ticket_draft(
    db: AsyncSession,
    *,
    case: Case,
    triage: TriageDraft,
    user: User,
    request_id: str,
) -> Ticket:
    recommendation = await recommend_assignee(db, triage.category)
    fields = triage.to_fields()
    draft = await get_draft_for_case(db, case.id)
    if draft is None:
        draft = Ticket(
            id=new_id("tkt"),
            case_id=case.id,
            status="DRAFT",
            version=1,
            fields=fields,
            missing_fields=list(triage.missing_fields),
        )
        db.add(draft)
    else:
        draft.version += 1
        draft.fields = fields
        draft.missing_fields = list(triage.missing_fields)
        draft.updated_at = utcnow()
    _apply_triage_fields(draft, fields)
    if recommendation.user is not None:
        draft.suggested_assignee_id = recommendation.user.id
        draft.suggested_assignee_reason = recommendation.reason
    await db.flush()
    await record_event(
        db,
        event_type="ticket.drafted",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=case.id,
        payload={
            "ticket_id": draft.id,
            "version": draft.version,
            "category": draft.category,
            "priority": draft.priority,
            "missing_fields": list(draft.missing_fields),
            "suggested_assignee_id": draft.suggested_assignee_id,
        },
    )
    case.status = "TICKET_DRAFT"
    case.current_node = "ticket_draft"
    case.intent = "ticket_triage"
    case.updated_at = utcnow()
    return draft


def _apply_triage_fields(ticket: Ticket, fields: dict[str, object]) -> None:
    for column in FIELD_COLUMNS:
        setattr(ticket, column, fields.get(column))
    ticket.fields = fields


async def _validate_assignee(db: AsyncSession, assignee_id: str | None) -> User | None:
    if not assignee_id:
        return None
    result = await db.execute(
        select(User).where(
            User.id == assignee_id,
            User.is_active.is_(True),
            User.role.in_(USER_REFERENCE_ROLES),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise AppError(
            "VALIDATION_ERROR",
            "处理人必须是可用的支持专员或管理员",
            422,
            {"field": "assignee_id"},
        )
    return user


def _validate_fields(values: dict[str, Any]) -> None:
    for key in ("title", "description", "priority_reason"):
        value = values.get(key)
        if value is not None and not str(value).strip():
            raise AppError(
                "VALIDATION_ERROR",
                f"{key} 不能为空",
                422,
                {"field": key},
            )
    if values.get("title"):
        values["title"] = str(values["title"]).strip()
    if values.get("description"):
        values["description"] = str(values["description"]).strip()
    if values.get("priority_reason"):
        values["priority_reason"] = str(values["priority_reason"]).strip()


def _conflict(ticket: Ticket) -> AppError:
    return AppError(
        "TYPE_CONFLICT",
        "工单已被其他操作更新，请刷新后重试",
        409,
        {"current_version": ticket.version, "current_status": ticket.status},
    )


def _snapshot(ticket: Ticket) -> dict[str, Any]:
    return {
        "title": ticket.title,
        "description": ticket.description,
        "category": ticket.category,
        "priority": ticket.priority,
        "priority_reason": ticket.priority_reason,
        "affected_system": ticket.affected_system,
        "environment": ticket.environment,
        "error_message": ticket.error_message,
        "urgency_reason": ticket.urgency_reason,
        "suggested_assignee_id": ticket.suggested_assignee_id,
        "assignee_id": ticket.assignee_id,
        "status": ticket.status,
        "version": ticket.version,
    }


async def confirm_ticket(
    db: AsyncSession,
    *,
    case: Case,
    payload: TicketCreate,
    user: User,
    request_id: str,
) -> Ticket:
    require_ticket_manage(user)
    if case.ticket_id:
        raise AppError("INVALID_STATE", "该 Case 已关联工单", 409)
    values = payload.fields.model_dump()
    _validate_fields(values)
    await _validate_assignee(db, values.get("suggested_assignee_id"))
    draft = await get_draft_for_case(db, case.id)
    if draft is not None and payload.draft_version is not None:
        if payload.draft_version != draft.version:
            raise _conflict(draft)
    if draft is None:
        draft = Ticket(
            id=new_id("tkt"),
            case_id=case.id,
            status="OPEN",
            version=1,
            fields=values,
            missing_fields=[],
        )
        db.add(draft)
        from_status = "DRAFT"
    else:
        from_status = draft.status
        _apply_form_fields(draft, values)
        draft.fields = values
        draft.status = "OPEN"
        draft.missing_fields = []
        draft.version += 1
        draft.updated_at = utcnow()
    if values.get("suggested_assignee_id"):
        draft.suggested_assignee_id = values["suggested_assignee_id"]
        draft.suggested_assignee_reason = "由确认人指定。"
    case.ticket_id = draft.id
    case.status = "TICKET_OPEN"
    case.current_node = "ticket"
    case.intent = "ticket_triage"
    case.updated_at = utcnow()
    await db.flush()
    await record_event(
        db,
        event_type="ticket.created",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=case.id,
        payload={
            "ticket_id": draft.id,
            "from_status": from_status,
            "to_status": draft.status,
            "category": draft.category,
            "priority": draft.priority,
            "version": draft.version,
        },
    )
    return draft


def _apply_form_fields(ticket: Ticket, values: dict[str, Any]) -> None:
    for column in FIELD_COLUMNS:
        if column in values:
            setattr(ticket, column, values[column])


async def update_ticket(
    db: AsyncSession,
    *,
    ticket: Ticket,
    payload: TicketUpdate,
    user: User,
    request_id: str,
) -> Ticket:
    require_ticket_manage(user)
    if payload.version != ticket.version:
        raise _conflict(ticket)
    changes = payload.fields.model_dump(exclude_unset=True)
    if not changes:
        return ticket
    _validate_fields(changes)
    if (
        "priority" in changes
        and changes["priority"] != ticket.priority
        and not changes.get("priority_reason")
    ):
        raise AppError(
            "VALIDATION_ERROR",
            "修改优先级时必须提供优先级理由",
            422,
            {"field": "priority_reason"},
        )
    for key in ("assignee_id", "suggested_assignee_id"):
        if key in changes:
            await _validate_assignee(db, changes[key])
    before = _snapshot(ticket)
    for column in FIELD_COLUMNS:
        if column in changes:
            setattr(ticket, column, changes[column])
    if "suggested_assignee_id" in changes:
        ticket.suggested_assignee_id = changes["suggested_assignee_id"]
        if changes["suggested_assignee_id"]:
            ticket.suggested_assignee_reason = "由处理人指定。"
    if "assignee_id" in changes:
        ticket.assignee_id = changes["assignee_id"]
    ticket.fields = {**(ticket.fields or {}), **changes}
    ticket.version += 1
    ticket.updated_at = utcnow()
    await db.flush()
    await record_event(
        db,
        event_type="ticket.updated",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=ticket.case_id,
        payload={
            "ticket_id": ticket.id,
            "changed_fields": sorted(changes.keys()),
            "before": before,
            "after": _snapshot(ticket),
        },
    )
    return ticket


async def transition_ticket(
    db: AsyncSession,
    *,
    ticket: Ticket,
    payload: TicketTransition,
    user: User,
    request_id: str,
) -> Ticket:
    require_ticket_manage(user)
    if payload.version != ticket.version:
        raise _conflict(ticket)
    to_status = payload.to_status
    allowed = TICKET_TRANSITIONS.get(ticket.status, frozenset())
    if to_status not in allowed:
        raise AppError(
            "INVALID_STATE",
            f"不能从 {ticket_status_label(ticket.status)} 流转到 {ticket_status_label(to_status)}",
            409,
            {
                "from_status": ticket.status,
                "to_status": to_status,
                "allowed": sorted(allowed),
            },
        )
    if to_status == "ASSIGNED":
        assignee_id = payload.assignee_id or ticket.assignee_id or ticket.suggested_assignee_id
        if not assignee_id:
            raise AppError(
                "VALIDATION_ERROR",
                "分派工单时必须指定处理人",
                422,
                {"field": "assignee_id"},
            )
        await _validate_assignee(db, assignee_id)
        ticket.assignee_id = assignee_id
    elif payload.assignee_id is not None:
        await _validate_assignee(db, payload.assignee_id)
        ticket.assignee_id = payload.assignee_id
    from_status = ticket.status
    ticket.status = to_status
    ticket.version += 1
    ticket.updated_at = utcnow()
    if payload.note:
        db.add(
            TicketNote(
                id=new_id("note"),
                ticket_id=ticket.id,
                author_id=user.id,
                content=payload.note.strip(),
            )
        )
    if to_status == "OPEN" and ticket.case_id:
        case_result = await db.execute(select(Case).where(Case.id == ticket.case_id))
        case = case_result.scalar_one_or_none()
        if case is not None:
            case.ticket_id = ticket.id
            case.status = "TICKET_OPEN"
            case.current_node = "ticket"
            case.updated_at = utcnow()
    await db.flush()
    await record_event(
        db,
        event_type="ticket.transitioned",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=ticket.case_id,
        payload={
            "ticket_id": ticket.id,
            "from_status": from_status,
            "to_status": to_status,
            "assignee_id": ticket.assignee_id,
            "note": payload.note,
            "version": ticket.version,
        },
    )
    return ticket


async def add_ticket_note(
    db: AsyncSession,
    *,
    ticket: Ticket,
    payload: TicketNoteCreate,
    user: User,
    request_id: str,
) -> TicketNoteOut:
    require_ticket_manage(user)
    content = payload.content.strip()
    if not content:
        raise AppError("VALIDATION_ERROR", "备注不能为空", 422)
    note = TicketNote(
        id=new_id("note"),
        ticket_id=ticket.id,
        author_id=user.id,
        content=content,
    )
    db.add(note)
    await db.flush()
    await record_event(
        db,
        event_type="ticket.updated",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=ticket.case_id,
        payload={"ticket_id": ticket.id, "kind": "note", "note_id": note.id},
    )
    return TicketNoteOut(
        id=note.id,
        ticket_id=note.ticket_id,
        author_id=note.author_id,
        author_name=user.name,
        content=note.content,
        created_at=note.created_at,
    )


async def list_assignees(db: AsyncSession) -> list[AssigneeOut]:
    result = await db.execute(
        select(User)
        .where(User.is_active.is_(True), User.role.in_(USER_REFERENCE_ROLES))
        .order_by(User.department.asc(), User.name.asc())
    )
    users = list(result.scalars().all())
    counts_result = await db.execute(
        select(Ticket.assignee_id, func.count(Ticket.id))
        .where(
            Ticket.status.in_(ACTIVE_STATUSES),
            Ticket.assignee_id.is_not(None),
        )
        .group_by(Ticket.assignee_id)
    )
    counts = {assignee_id: count for assignee_id, count in counts_result.all()}
    return [
        AssigneeOut(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,
            role_label=ROLE_LABELS.get(user.role, user.role),
            department=user.department,
            open_ticket_count=counts.get(user.id, 0),
        )
        for user in users
    ]


async def list_tickets(
    db: AsyncSession,
    *,
    user: User,
    limit: int,
    cursor: str | None,
    status: str | None,
    category: str | None,
    priority: str | None,
    assignee_id: str | None,
    query: str | None,
) -> tuple[list[TicketOut], str | None]:
    offset = 0
    if cursor:
        try:
            offset = max(0, int(cursor))
        except ValueError as exc:
            raise AppError("VALIDATION_ERROR", "cursor 不合法", 422) from exc
    statement = select(Ticket).where(Ticket.status != "DRAFT")
    if not has_permission(user.role, "case:read_all"):
        statement = statement.join(Case, Case.id == Ticket.case_id).where(
            Case.requester_id == user.id
        )
    if status:
        statement = statement.where(Ticket.status == status)
    if category:
        statement = statement.where(Ticket.category == category)
    if priority:
        statement = statement.where(Ticket.priority == priority)
    if assignee_id:
        statement = statement.where(Ticket.assignee_id == assignee_id)
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(
            or_(Ticket.title.ilike(pattern), Ticket.description.ilike(pattern))
        )
    statement = (
        statement.order_by(Ticket.updated_at.desc(), Ticket.id.desc())
        .offset(offset)
        .limit(limit + 1)
    )
    result = await db.execute(statement)
    tickets = list(result.scalars().all())
    has_more = len(tickets) > limit
    visible = tickets[:limit]
    next_cursor = str(offset + limit) if has_more else None
    return await to_ticket_outs(db, visible), next_cursor


async def get_assignee_or_404(db: AsyncSession, assignee_id: str) -> User:
    result = await db.execute(select(User).where(User.id == assignee_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise AppError("NOT_FOUND", "处理人不存在", 404)
    return user


def ticket_draft_payload(ticket_out: TicketOut) -> dict[str, Any]:
    payload = ticket_out.model_dump(mode="json")
    payload["ticket_id"] = ticket_out.id
    return payload
