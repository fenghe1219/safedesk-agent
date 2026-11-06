from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.rbac import has_permission
from app.core.security import as_utc, new_id, utcnow
from app.models.action import ActionRequest, Approval, ToolExecution
from app.models.audit import AuditEvent
from app.models.case import Case
from app.models.user import User
from app.schemas.action import (
    ActionDecisionResponse,
    ActionOut,
    ApprovalDetailOut,
    ApprovalListItemOut,
    ApprovalOut,
    CaseActionOut,
    ToolExecutionOut,
)
from app.services.admin_settings import get_runtime_config
from app.services.audit import record_event
from app.services.case_service import (
    CASE_STATUS_LABELS,
    get_accessible_case,
    to_case_out,
    to_timeline_event,
)
from app.services.tools import (
    ReadToolResult,
    ToolRuntimeError,
    canonical_args_hash,
    execute_mock_write,
    get_kill_switch,
    get_tool_policy,
    get_tool_spec,
    validate_tool_args,
    verify_mock_write,
)
from app.services.workflow import ensure_await_approval_checkpoint, record_checkpoint

ACTION_STATUS_LABELS: dict[str, str] = {
    "PROPOSED": "已提议",
    "AWAITING_APPROVAL": "等待审批",
    "APPROVED": "已批准",
    "EXECUTING": "执行中",
    "SUCCEEDED": "执行成功",
    "FAILED": "执行失败",
    "REJECTED": "已拒绝",
    "EXPIRED": "已过期",
    "CANCELLED": "已取消",
}
APPROVAL_STATUS_LABELS: dict[str, str] = {
    "PENDING": "待审批",
    "APPROVED": "已批准",
    "REJECTED": "已拒绝",
    "EXPIRED": "已过期",
    "CANCELLED": "已取消",
}
RISK_LABELS: dict[str, str] = {"LOW": "低风险", "MEDIUM": "中风险", "HIGH": "高风险"}
ACTIVE_ACTION_STATUSES = ("PROPOSED", "AWAITING_APPROVAL", "APPROVED", "EXECUTING")

_VPN_WRITE_PATTERN = re.compile(
    r"(?:(?:帮我|请|需要|立即|现在).{0,8}(?:重置|重新签发|更新).{0,8}证书)"
    r"|(?:证书.{0,8}(?:重置|重新签发))"
    r"|(?:重置.{0,8}vpn.{0,8}证书)",
    re.IGNORECASE,
)
_GRANT_PATTERN = re.compile(
    r"(?:(?:申请|帮我|请|需要).{0,10}(?:开通|授予|授权|添加).{0,12}(?:权限|访问|角色))"
    r"|(?:(?:开通|授予|授权).{0,12}(?:应用|系统|权限))"
    r"|(?:(?:申请|需要).{0,16}(?:权限|访问|角色))",
    re.IGNORECASE,
)
_KNOWN_APPS = ("Visio", "Jira", "Confluence", "GitLab", "Figma", "飞书", "企业微信")


@dataclass(frozen=True)
class ActionIntent:
    tool_name: str
    diagnostic_tool: str
    diagnostic_args: dict[str, Any]
    args: dict[str, Any]


@dataclass(frozen=True)
class ActionExecutionOutcome:
    approval: Approval
    action: ActionRequest
    case: Case
    execution: ToolExecution | None
    message: str


def action_status_label(status: str) -> str:
    return ACTION_STATUS_LABELS.get(status, status)


def approval_status_label(status: str) -> str:
    return APPROVAL_STATUS_LABELS.get(status, status)


def risk_label(risk_level: str) -> str:
    return RISK_LABELS.get(risk_level, risk_level)


def detect_action_intent(content: str, case: Case) -> ActionIntent | None:
    lowered = content.lower()
    if ("vpn" in lowered or "证书" in content) and _VPN_WRITE_PATTERN.search(content):
        return ActionIntent(
            tool_name="reset_vpn_certificate",
            diagnostic_tool="get_vpn_status",
            diagnostic_args={"user_id": case.requester_id},
            args={"user_id": case.requester_id, "reason": content[:300]},
        )
    if _GRANT_PATTERN.search(content) and "安装" not in content:
        app_name = next((app for app in _KNOWN_APPS if app.lower() in lowered), "内部应用")
        return ActionIntent(
            tool_name="grant_app_access",
            diagnostic_tool="get_account_status",
            diagnostic_args={"user_id": case.requester_id},
            args={
                "user_id": case.requester_id,
                "app_name": app_name,
                "role": "user",
                "expires_in_days": 30,
                "reason": content[:300],
            },
        )
    return None


async def get_latest_action_for_case(
    db: AsyncSession, case_id: str
) -> ActionRequest | None:
    result = await db.execute(
        select(ActionRequest)
        .where(ActionRequest.case_id == case_id)
        .order_by(ActionRequest.created_at.desc(), ActionRequest.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_active_action_for_case(
    db: AsyncSession, case_id: str
) -> ActionRequest | None:
    result = await db.execute(
        select(ActionRequest)
        .where(
            ActionRequest.case_id == case_id,
            ActionRequest.status.in_(ACTIVE_ACTION_STATUSES),
        )
        .order_by(ActionRequest.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_action_proposal(
    db: AsyncSession,
    *,
    case: Case,
    user: User,
    intent: ActionIntent,
    diagnostic: ReadToolResult,
    evidence_ids: list[str],
    request_id: str,
) -> tuple[ActionRequest, Approval]:
    existing = await get_active_action_for_case(db, case.id)
    if existing is not None:
        approval = await _get_approval_for_action(db, existing.id)
        if approval is None:
            raise AppError("INVALID_STATE", "动作缺少审批记录", 409)
        return existing, approval

    spec = get_tool_spec(intent.tool_name)
    args = validate_tool_args(intent.tool_name, intent.args)
    args_hash = canonical_args_hash(intent.tool_name, args)
    runtime = await get_runtime_config(db)
    now = utcnow()
    expires_at = now + timedelta(seconds=runtime.approval_ttl_seconds)
    action = ActionRequest(
        id=new_id("act"),
        case_id=case.id,
        tool_name=spec.name,
        tool_label=spec.label,
        tool_type=spec.tool_type,
        risk_level=spec.risk_level,
        args=args,
        args_hash=args_hash,
        rationale=f"{diagnostic.summary} 该动作只处理当前用户，执行前需要人工确认。",
        impact=(
            f"仅影响当前用户 {user.name}（{case.requester_id}）；"
            f"动作范围限定为「{spec.label}」，不会扩展到其他用户。"
        ),
        verification_plan="执行完成后调用只读工具复核证书或权限状态，并记录验证结果。",
        rollback_plan="如执行结果异常，停止后续自动操作并转工单由桌面支持人工恢复。",
        evidence_ids=[*evidence_ids, diagnostic.evidence_id],
        status="AWAITING_APPROVAL",
        requested_by_id=case.requester_id,
        idempotency_key=f"{case.id}:{intent.tool_name}:{new_id('try')}",
        expires_at=expires_at,
        version=1,
    )
    db.add(action)
    await db.flush()
    approval = Approval(
        id=new_id("apr"),
        action_id=action.id,
        status="PENDING",
        args_hash=args_hash,
        requested_at=now,
        expires_at=expires_at,
        version=1,
    )
    db.add(approval)
    await db.flush()
    await record_event(
        db,
        event_type="action.proposed",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=case.id,
        payload={
            "action_id": action.id,
            "tool_name": action.tool_name,
            "tool_label": action.tool_label,
            "args": args,
            "args_hash": args_hash,
            "risk_level": action.risk_level,
            "rationale": action.rationale,
            "evidence_ids": action.evidence_ids,
            "idempotency_key": action.idempotency_key,
            "approval_id": approval.id,
            "expires_at": expires_at.isoformat(),
        },
    )
    await record_event(
        db,
        event_type="approval.requested",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=case.id,
        payload={
            "approval_id": approval.id,
            "action_id": action.id,
            "tool_name": action.tool_name,
            "expires_at": expires_at.isoformat(),
        },
    )
    case.action_id = action.id
    case.status = "AWAITING_APPROVAL"
    case.current_node = "await_approval"
    case.intent = "action_approval"
    case.updated_at = now
    await db.flush()
    await record_checkpoint(
        db,
        case=case,
        node="propose_action",
        state={
            "action_id": action.id,
            "approval_id": approval.id,
            "tool_name": action.tool_name,
            "risk_level": action.risk_level,
            "evidence_ids": action.evidence_ids,
        },
    )
    await record_checkpoint(
        db,
        case=case,
        node="await_approval",
        status="waiting",
        state={
            "action_id": action.id,
            "action_status": action.status,
            "approval_id": approval.id,
            "approval_status": approval.status,
            "expires_at": expires_at.isoformat(),
        },
    )
    return action, approval


def _is_expired(value: Any) -> bool:
    return as_utc(value) <= utcnow()


def _scope_allows(user: User, action: ActionRequest, requester: User) -> bool:
    scopes = user.approval_scopes or {}
    tools = scopes.get("tools") or []
    departments = scopes.get("departments") or []
    if tools and "*" not in tools and action.tool_name not in tools:
        return False
    if departments and "*" not in departments and requester.department not in departments:
        return False
    return True


def _can_view_approval(user: User, action: ActionRequest, requester: User) -> bool:
    return has_permission(user.role, "approval:view") and _scope_allows(
        user, action, requester
    )


async def _names_for_ids(db: AsyncSession, ids: list[str]) -> dict[str, str]:
    if not ids:
        return {}
    result = await db.execute(select(User.id, User.name).where(User.id.in_(set(ids))))
    return {row[0]: row[1] for row in result.all()}


def to_execution_out(execution: ToolExecution | None) -> ToolExecutionOut | None:
    if execution is None:
        return None
    return ToolExecutionOut(
        id=execution.id,
        action_id=execution.action_id,
        tool_name=execution.tool_name,
        status=execution.status,
        idempotency_key=execution.idempotency_key,
        args_hash=execution.args_hash,
        output=dict(execution.output or {}),
        result_summary=execution.result_summary,
        verification=dict(execution.verification or {}),
        error_code=execution.error_code,
        error_message=execution.error_message,
        started_at=execution.started_at,
        finished_at=execution.finished_at,
    )


async def to_approval_out(db: AsyncSession, approval: Approval) -> ApprovalOut:
    names = await _names_for_ids(
        db, [approval.approver_id] if approval.approver_id else []
    )
    return ApprovalOut(
        id=approval.id,
        action_id=approval.action_id,
        status=approval.status,
        status_label=approval_status_label(approval.status),
        args_hash=approval.args_hash,
        approver_id=approval.approver_id,
        approver_name=names.get(approval.approver_id or ""),
        decision_reason=approval.decision_reason,
        requested_at=approval.requested_at,
        expires_at=approval.expires_at,
        decided_at=approval.decided_at,
        version=approval.version,
    )


async def to_action_out(db: AsyncSession, action: ActionRequest) -> ActionOut:
    names = await _names_for_ids(db, [action.requested_by_id])
    return ActionOut(
        id=action.id,
        case_id=action.case_id,
        tool_name=action.tool_name,
        tool_label=action.tool_label,
        tool_type=action.tool_type,
        risk_level=action.risk_level,
        risk_label=risk_label(action.risk_level),
        status=action.status,
        status_label=action_status_label(action.status),
        args=dict(action.args or {}),
        args_hash=action.args_hash,
        rationale=action.rationale,
        impact=action.impact,
        verification_plan=action.verification_plan,
        rollback_plan=action.rollback_plan,
        evidence_ids=list(action.evidence_ids or []),
        requested_by_id=action.requested_by_id,
        requested_by_name=names.get(action.requested_by_id, action.requested_by_id),
        expires_at=action.expires_at,
        version=action.version,
        created_at=action.created_at,
        updated_at=action.updated_at,
    )


async def _get_approval_for_action(
    db: AsyncSession, action_id: str
) -> Approval | None:
    result = await db.execute(select(Approval).where(Approval.action_id == action_id))
    return result.scalar_one_or_none()


async def _get_execution_for_action(
    db: AsyncSession, action_id: str
) -> ToolExecution | None:
    result = await db.execute(
        select(ToolExecution).where(ToolExecution.action_id == action_id)
    )
    return result.scalar_one_or_none()


async def _get_approval_bundle(
    db: AsyncSession, approval_id: str
) -> tuple[Approval, ActionRequest, Case, User]:
    result = await db.execute(
        select(Approval, ActionRequest, Case, User)
        .join(ActionRequest, Approval.action_id == ActionRequest.id)
        .join(Case, ActionRequest.case_id == Case.id)
        .join(User, ActionRequest.requested_by_id == User.id)
        .where(Approval.id == approval_id)
    )
    row = result.one_or_none()
    if row is None:
        raise AppError("NOT_FOUND", "审批记录不存在", 404)
    return row[0], row[1], row[2], row[3]


async def _expire_bundle(
    db: AsyncSession,
    *,
    approval: Approval,
    action: ActionRequest,
    case: Case,
    request_id: str,
) -> None:
    now = utcnow()
    approval.status = "EXPIRED"
    approval.version += 1
    approval.updated_at = now
    action.status = "EXPIRED"
    action.version += 1
    action.updated_at = now
    case.status = "EXPIRED"
    case.current_node = "approval_expired"
    case.updated_at = now
    await record_event(
        db,
        event_type="approval.expired",
        actor_id=None,
        actor_role=None,
        request_id=request_id,
        case_id=case.id,
        payload={
            "approval_id": approval.id,
            "action_id": action.id,
            "tool_name": action.tool_name,
            "expires_at": as_utc(approval.expires_at).isoformat(),
        },
        result="expired",
    )
    await db.flush()
    await record_checkpoint(
        db,
        case=case,
        node="approval_expired",
        status="expired",
        state={
            "action_id": action.id,
            "action_status": action.status,
            "approval_id": approval.id,
            "approval_status": approval.status,
        },
    )


async def expire_stale_approvals(
    db: AsyncSession, *, request_id: str = "system:approval-expiry"
) -> int:
    result = await db.execute(
        select(Approval, ActionRequest, Case)
        .join(ActionRequest, Approval.action_id == ActionRequest.id)
        .join(Case, ActionRequest.case_id == Case.id)
        .where(Approval.status == "PENDING")
    )
    expired = 0
    for approval, action, case in result.all():
        if not _is_expired(approval.expires_at):
            continue
        await _expire_bundle(
            db,
            approval=approval,
            action=action,
            case=case,
            request_id=request_id,
        )
        expired += 1
    return expired


async def approval_blockers(
    db: AsyncSession,
    *,
    user: User,
    action: ActionRequest,
    approval: Approval,
    case: Case,
    requester: User,
) -> list[str]:
    blockers: list[str] = []
    if not has_permission(user.role, "approval:decide"):
        blockers.append("当前角色没有审批决策权限")
    if user.id == action.requested_by_id:
        blockers.append("申请人不能审批自己的动作")
    if not _scope_allows(user, action, requester):
        blockers.append("该动作不在你的工具或部门审批范围内")
    if approval.status != "PENDING":
        blockers.append(f"审批状态为 {approval_status_label(approval.status)}")
    if action.status != "AWAITING_APPROVAL":
        blockers.append(f"动作状态为 {action_status_label(action.status)}")
    if _is_expired(approval.expires_at):
        blockers.append("审批已过期，不能再执行")
    if case.status == "CANCELLED":
        blockers.append("Case 已关闭，不能继续执行")
    try:
        actual_hash = canonical_args_hash(action.tool_name, dict(action.args or {}))
        if approval.args_hash != actual_hash or action.args_hash != actual_hash:
            blockers.append("动作参数与审批快照不一致")
    except AppError:
        blockers.append("动作参数无法重新校验")
    enabled, _ = await get_tool_policy(db, action.tool_name)
    if not enabled:
        blockers.append("工具已被管理员停用")
    kill_switch, kill_reason, _ = await get_kill_switch(db)
    if kill_switch:
        blockers.append(
            f"Kill Switch 已开启：{kill_reason}" if kill_reason else "Kill Switch 已开启"
        )
    return blockers


async def _can_decide(
    db: AsyncSession,
    *,
    user: User,
    action: ActionRequest,
    approval: Approval,
    case: Case,
    requester: User,
) -> bool:
    return not await approval_blockers(
        db,
        user=user,
        action=action,
        approval=approval,
        case=case,
        requester=requester,
    )


async def _require_decider(
    db: AsyncSession,
    *,
    user: User,
    action: ActionRequest,
    approval: Approval,
    case: Case,
    requester: User,
    request_id: str,
) -> None:
    if not has_permission(user.role, "approval:decide"):
        raise AppError("FORBIDDEN", "当前角色没有审批决策权限", 403)
    if user.id == action.requested_by_id:
        raise AppError("SELF_APPROVAL_FORBIDDEN", "申请人不能审批自己的动作", 403)
    if not _scope_allows(user, action, requester):
        raise AppError("OUT_OF_SCOPE", "该动作不在你的审批范围内", 403)
    if case.status == "CANCELLED":
        raise AppError("CASE_CLOSED", "Case 已关闭，不能继续审批", 409)
    if approval.status == "PENDING" and action.status != "AWAITING_APPROVAL":
        raise AppError("INVALID_STATE", "动作状态与审批状态不一致", 409)
    if _is_expired(approval.expires_at):
        if approval.status == "PENDING":
            await _expire_bundle(
                db,
                approval=approval,
                action=action,
                case=case,
                request_id=request_id,
            )
            await db.commit()
        raise AppError("APPROVAL_EXPIRED", "审批已过期，请重新发起动作", 409)


def _snapshot_matches(action: ActionRequest, approval: Approval) -> bool:
    try:
        actual_hash = canonical_args_hash(action.tool_name, dict(action.args or {}))
    except AppError:
        return False
    return approval.args_hash == actual_hash == action.args_hash


def _outcome(
    *,
    approval: Approval,
    action: ActionRequest,
    case: Case,
    execution: ToolExecution | None,
    message: str,
) -> ActionExecutionOutcome:
    return ActionExecutionOutcome(
        approval=approval,
        action=action,
        case=case,
        execution=execution,
        message=message,
    )


async def list_approvals(
    db: AsyncSession, *, user: User, status: str | None = None
) -> list[ApprovalListItemOut]:
    statement = (
        select(Approval, ActionRequest, Case, User)
        .join(ActionRequest, Approval.action_id == ActionRequest.id)
        .join(Case, ActionRequest.case_id == Case.id)
        .join(User, ActionRequest.requested_by_id == User.id)
    )
    if status is not None:
        statement = statement.where(Approval.status == status)
    result = await db.execute(statement)
    items: list[ApprovalListItemOut] = []
    for approval, action, case, requester in result.all():
        if not _can_view_approval(user, action, requester):
            continue
        can_decide = await _can_decide(
            db,
            user=user,
            action=action,
            approval=approval,
            case=case,
            requester=requester,
        )
        items.append(
            ApprovalListItemOut(
                id=approval.id,
                action_id=action.id,
                case_id=case.id,
                case_title=case.title,
                requester_id=requester.id,
                requester_name=requester.name,
                tool_name=action.tool_name,
                tool_label=action.tool_label,
                risk_level=action.risk_level,
                risk_label=risk_label(action.risk_level),
                impact=action.impact,
                status=approval.status,
                status_label=approval_status_label(approval.status),
                requested_at=approval.requested_at,
                expires_at=approval.expires_at,
                decided_at=approval.decided_at,
                can_decide=can_decide,
            )
        )
    risk_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    items.sort(key=lambda item: (risk_order.get(item.risk_level, 9), item.expires_at))
    return items


async def get_approval_detail(
    db: AsyncSession, *, user: User, approval_id: str
) -> ApprovalDetailOut:
    approval, action, case, requester = await _get_approval_bundle(db, approval_id)
    if not _can_view_approval(user, action, requester):
        raise AppError("NOT_FOUND", "审批记录不存在", 404)
    execution = await _get_execution_for_action(db, action.id)
    timeline_result = await db.execute(
        select(AuditEvent)
        .where(AuditEvent.case_id == case.id)
        .order_by(AuditEvent.created_at.asc())
    )
    can_decide = await _can_decide(
        db,
        user=user,
        action=action,
        approval=approval,
        case=case,
        requester=requester,
    )
    blockers = await approval_blockers(
        db,
        user=user,
        action=action,
        approval=approval,
        case=case,
        requester=requester,
    )
    return ApprovalDetailOut(
        approval=await to_approval_out(db, approval),
        action=await to_action_out(db, action),
        case=to_case_out(case),
        execution=to_execution_out(execution),
        timeline=[to_timeline_event(event) for event in timeline_result.scalars().all()],
        permissions={"can_view": True, "can_decide": can_decide},
        blockers=blockers,
    )


async def get_case_action(
    db: AsyncSession, *, user: User, case_id: str
) -> CaseActionOut:
    case = await get_accessible_case(db, user, case_id)
    action = await get_latest_action_for_case(db, case.id)
    if action is None:
        raise AppError("NOT_FOUND", "该 Case 暂无动作", 404)
    approval = await _get_approval_for_action(db, action.id)
    if approval is None:
        raise AppError("INVALID_STATE", "动作缺少审批记录", 409)
    if action.status in ACTIVE_ACTION_STATUSES:
        await ensure_await_approval_checkpoint(
            db, case=case, action=action, approval=approval
        )
    requester_result = await db.execute(select(User).where(User.id == action.requested_by_id))
    requester = requester_result.scalar_one()
    execution = await _get_execution_for_action(db, action.id)
    can_decide = await _can_decide(
        db,
        user=user,
        action=action,
        approval=approval,
        case=case,
        requester=requester,
    )
    blockers = await approval_blockers(
        db,
        user=user,
        action=action,
        approval=approval,
        case=case,
        requester=requester,
    )
    action_out = await to_action_out(db, action)
    return CaseActionOut(
        **action_out.model_dump(),
        case_status=case.status,
        case_status_label=CASE_STATUS_LABELS.get(case.status, case.status),
        approval=await to_approval_out(db, approval),
        execution=to_execution_out(execution),
        permissions={"can_view": True, "can_decide": can_decide},
        blockers=blockers,
    )


async def _decision_response(
    db: AsyncSession, outcome: ActionExecutionOutcome
) -> ActionDecisionResponse:
    return ActionDecisionResponse(
        approval=await to_approval_out(db, outcome.approval),
        action=await to_action_out(db, outcome.action),
        case=to_case_out(outcome.case),
        execution=to_execution_out(outcome.execution),
        message=outcome.message,
    )


async def approve_action(
    db: AsyncSession,
    *,
    approval_id: str,
    user: User,
    expected_args_hash: str,
    approval_version: int,
    reason: str | None,
    request_id: str,
) -> ActionExecutionOutcome:
    approval, action, case, requester = await _get_approval_bundle(db, approval_id)
    await _require_decider(
        db,
        user=user,
        action=action,
        approval=approval,
        case=case,
        requester=requester,
        request_id=request_id,
    )
    if expected_args_hash not in {approval.args_hash, action.args_hash} or not (
        _snapshot_matches(action, approval)
    ):
        raise AppError(
            "TYPE_CONFLICT",
            "动作参数已变化，审批快照不再匹配，请重新发起动作",
            409,
        )
    if approval.status == "APPROVED":
        execution = await _get_execution_for_action(db, action.id)
        if execution is not None:
            await record_event(
                db,
                event_type="tool.duplicate_blocked",
                actor_id=user.id,
                actor_role=user.role,
                request_id=request_id,
                case_id=case.id,
                payload={
                    "approval_id": approval.id,
                    "action_id": action.id,
                    "execution_id": execution.id,
                    "reason": "repeat_approval_returned_existing_execution",
                },
            )
            return _outcome(
                approval=approval,
                action=action,
                case=case,
                execution=execution,
                message="该动作已经批准并执行，未重复调用工具。",
            )
        return await resume_approved_action(
            db, action=action, user=user, request_id=request_id
        )
    if approval.status != "PENDING":
        raise AppError(
            "INVALID_STATE",
            f"审批当前为 {approval_status_label(approval.status)}，不能批准",
            409,
        )
    if approval_version != approval.version:
        raise AppError("VERSION_CONFLICT", "审批版本已变化，请刷新后重试", 409)
    enabled, _ = await get_tool_policy(db, action.tool_name)
    if not enabled:
        raise AppError("TOOL_DISABLED", "工具已被管理员停用，不能执行", 409)
    kill_switch, kill_reason, _ = await get_kill_switch(db)
    if kill_switch:
        detail = f"：{kill_reason}" if kill_reason else ""
        raise AppError("KILL_SWITCH_ENABLED", f"Kill Switch 已开启{detail}", 409)

    now = utcnow()
    updated = await db.execute(
        update(Approval)
        .where(
            Approval.id == approval.id,
            Approval.status == "PENDING",
            Approval.version == approval_version,
        )
        .values(
            status="APPROVED",
            approver_id=user.id,
            decision_reason=reason,
            decided_at=now,
            version=Approval.version + 1,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if updated.rowcount != 1:
        await db.refresh(approval)
        await db.refresh(action)
        execution = await _get_execution_for_action(db, action.id)
        if approval.status == "APPROVED" and execution is not None:
            await record_event(
                db,
                event_type="tool.duplicate_blocked",
                actor_id=user.id,
                actor_role=user.role,
                request_id=request_id,
                case_id=case.id,
                payload={
                    "approval_id": approval.id,
                    "action_id": action.id,
                    "execution_id": execution.id,
                    "reason": "concurrent_repeat_approval",
                },
            )
            return _outcome(
                approval=approval,
                action=action,
                case=case,
                execution=execution,
                message="该动作已经批准并执行，未重复调用工具。",
            )
        raise AppError("VERSION_CONFLICT", "审批状态已变化，请刷新后重试", 409)
    await db.execute(
        update(ActionRequest)
        .where(ActionRequest.id == action.id, ActionRequest.status == "AWAITING_APPROVAL")
        .values(status="APPROVED", version=ActionRequest.version + 1, updated_at=now)
        .execution_options(synchronize_session=False)
    )
    await db.refresh(approval)
    await db.refresh(action)
    await record_event(
        db,
        event_type="approval.approved",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=case.id,
        payload={
            "approval_id": approval.id,
            "action_id": action.id,
            "tool_name": action.tool_name,
            "args_hash": action.args_hash,
            "reason": reason,
        },
    )
    await record_checkpoint(
        db,
        case=case,
        node="approval_decided",
        status="approved",
        state={
            "action_id": action.id,
            "approval_id": approval.id,
            "approver_id": user.id,
            "args_hash": action.args_hash,
        },
    )
    await db.flush()
    return await resume_approved_action(
        db, action=action, user=user, request_id=request_id
    )


async def reject_action(
    db: AsyncSession,
    *,
    approval_id: str,
    user: User,
    approval_version: int,
    reason: str,
    request_id: str,
) -> ActionExecutionOutcome:
    approval, action, case, requester = await _get_approval_bundle(db, approval_id)
    await _require_decider(
        db,
        user=user,
        action=action,
        approval=approval,
        case=case,
        requester=requester,
        request_id=request_id,
    )
    if not _snapshot_matches(action, approval):
        raise AppError(
            "TYPE_CONFLICT",
            "动作参数已变化，审批快照不再匹配，请重新发起动作",
            409,
        )
    if approval.status == "REJECTED":
        return _outcome(
            approval=approval,
            action=action,
            case=case,
            execution=None,
            message="该动作已经拒绝，未执行工具。",
        )
    if approval.status != "PENDING":
        raise AppError(
            "INVALID_STATE",
            f"审批当前为 {approval_status_label(approval.status)}，不能拒绝",
            409,
        )
    if approval_version != approval.version:
        raise AppError("VERSION_CONFLICT", "审批版本已变化，请刷新后重试", 409)

    now = utcnow()
    updated = await db.execute(
        update(Approval)
        .where(
            Approval.id == approval.id,
            Approval.status == "PENDING",
            Approval.version == approval_version,
        )
        .values(
            status="REJECTED",
            approver_id=user.id,
            decision_reason=reason,
            decided_at=now,
            version=Approval.version + 1,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if updated.rowcount != 1:
        raise AppError("VERSION_CONFLICT", "审批状态已变化，请刷新后重试", 409)
    await db.execute(
        update(ActionRequest)
        .where(ActionRequest.id == action.id, ActionRequest.status == "AWAITING_APPROVAL")
        .values(status="REJECTED", version=ActionRequest.version + 1, updated_at=now)
        .execution_options(synchronize_session=False)
    )
    await db.refresh(approval)
    await db.refresh(action)
    case.status = "REJECTED"
    case.current_node = "approval_rejected"
    case.updated_at = now
    await record_event(
        db,
        event_type="approval.rejected",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=case.id,
        payload={
            "approval_id": approval.id,
            "action_id": action.id,
            "tool_name": action.tool_name,
            "reason": reason,
        },
        result="rejected",
    )
    await db.flush()
    await record_checkpoint(
        db,
        case=case,
        node="approval_decided",
        status="rejected",
        state={
            "action_id": action.id,
            "approval_id": approval.id,
            "approver_id": user.id,
            "reason": reason,
        },
    )
    return _outcome(
        approval=approval,
        action=action,
        case=case,
        execution=None,
        message="已拒绝该动作，工具不会执行。",
    )


async def _fail_action(
    db: AsyncSession,
    *,
    action: ActionRequest,
    case: Case,
    user: User,
    request_id: str,
    code: str,
    message: str,
    execution: ToolExecution,
) -> ToolExecution:
    now = utcnow()
    execution.status = "FAILED"
    execution.error_code = code
    execution.error_message = message
    execution.finished_at = now
    action.status = "FAILED"
    action.version += 1
    action.updated_at = now
    case.status = "FAILED"
    case.current_node = "execution_failed"
    case.updated_at = now
    await record_event(
        db,
        event_type="tool.failed",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=case.id,
        payload={
            "action_id": action.id,
            "execution_id": execution.id,
            "tool_name": action.tool_name,
            "error_code": code,
            "error_message": message,
        },
        result="failed",
    )
    await db.flush()
    await record_checkpoint(
        db,
        case=case,
        node="execute_action",
        status="failed",
        state={
            "action_id": action.id,
            "execution_id": execution.id,
            "error_code": code,
            "error_message": message,
        },
    )
    return execution


async def _finish_execution_success(
    db: AsyncSession,
    *,
    action: ActionRequest,
    case: Case,
    user: User,
    request_id: str,
    execution: ToolExecution,
    output: dict[str, Any],
    summary: str,
    verification: dict[str, Any],
) -> ToolExecution:
    now = utcnow()
    execution.status = "SUCCEEDED"
    execution.output = output
    execution.result_summary = summary
    execution.verification = verification
    execution.finished_at = now
    action.status = "SUCCEEDED"
    action.version += 1
    action.updated_at = now
    case.status = "RESOLVED"
    case.current_node = "resolved"
    case.updated_at = now
    await record_event(
        db,
        event_type="tool.executed",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=case.id,
        payload={
            "action_id": action.id,
            "execution_id": execution.id,
            "tool_name": action.tool_name,
            "args_hash": action.args_hash,
            "result_summary": summary,
            "output": output,
        },
    )
    verify_event = await record_event(
        db,
        event_type="action.verified",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=case.id,
        payload={
            "action_id": action.id,
            "execution_id": execution.id,
            "verification": verification,
        },
    )
    await record_event(
        db,
        event_type="case.resolved",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=case.id,
        payload={
            "action_id": action.id,
            "execution_id": execution.id,
            "verification_event_id": verify_event.id,
        },
    )
    await db.flush()
    await record_checkpoint(
        db,
        case=case,
        node="execute_action",
        state={
            "action_id": action.id,
            "execution_id": execution.id,
            "output": output,
        },
    )
    await record_checkpoint(
        db,
        case=case,
        node="verify_action",
        state={
            "action_id": action.id,
            "execution_id": execution.id,
            "verification_event_id": verify_event.id,
            "verification": verification,
        },
    )
    await record_checkpoint(
        db,
        case=case,
        node="resolved",
        state={"action_id": action.id, "execution_id": execution.id},
    )
    return execution


async def resume_approved_action(
    db: AsyncSession,
    *,
    action: ActionRequest,
    user: User,
    request_id: str,
) -> ActionExecutionOutcome:
    case_result = await db.execute(select(Case).where(Case.id == action.case_id))
    case = case_result.scalar_one_or_none()
    if case is None:
        raise AppError("NOT_FOUND", "动作关联的 Case 不存在", 404)
    approval = await _get_approval_for_action(db, action.id)
    if approval is None:
        raise AppError("INVALID_STATE", "动作缺少审批记录", 409)
    existing = await _get_execution_for_action(db, action.id)
    if existing is not None:
        return _outcome(
            approval=approval,
            action=action,
            case=case,
            execution=existing,
            message="该动作已有执行记录，未重复调用工具。",
        )
    if case.status == "CANCELLED":
        raise AppError("CASE_CLOSED", "Case 已关闭，不能执行动作", 409)
    if _is_expired(action.expires_at):
        await _expire_bundle(
            db,
            approval=approval,
            action=action,
            case=case,
            request_id=request_id,
        )
        await db.commit()
        raise AppError("APPROVAL_EXPIRED", "审批已过期，不能执行动作", 409)
    if action.status not in {"APPROVED", "EXECUTING"}:
        raise AppError("INVALID_STATE", "动作状态不允许执行", 409)

    now = utcnow()
    if action.status == "APPROVED":
        claimed = await db.execute(
            update(ActionRequest)
            .where(
                ActionRequest.id == action.id,
                ActionRequest.status == "APPROVED",
            )
            .values(status="EXECUTING", version=ActionRequest.version + 1, updated_at=now)
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            await db.refresh(action)
            existing = await _get_execution_for_action(db, action.id)
            if existing is not None:
                return _outcome(
                    approval=approval,
                    action=action,
                    case=case,
                    execution=existing,
                    message="该动作已有执行记录，未重复调用工具。",
                )
            raise AppError("INVALID_STATE", "动作已被其他请求接管", 409)
        await db.refresh(action)
    case.status = "EXECUTING"
    case.current_node = "tool_executing"
    case.updated_at = now
    await record_event(
        db,
        event_type="tool.executing",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=case.id,
        payload={
            "action_id": action.id,
            "tool_name": action.tool_name,
            "args_hash": action.args_hash,
            "idempotency_key": action.idempotency_key,
        },
    )
    await db.flush()
    await record_checkpoint(
        db,
        case=case,
        node="execute_action",
        status="running",
        state={
            "action_id": action.id,
            "tool_name": action.tool_name,
            "idempotency_key": action.idempotency_key,
        },
    )
    execution = ToolExecution(
        id=new_id("exec"),
        action_id=action.id,
        tool_name=action.tool_name,
        status="RUNNING",
        idempotency_key=action.idempotency_key,
        args_hash=action.args_hash,
        request_id=request_id,
        started_at=now,
    )
    db.add(execution)
    await db.flush()

    enabled, mock_mode = await get_tool_policy(db, action.tool_name)
    if not enabled:
        execution = await _fail_action(
            db,
            action=action,
            case=case,
            user=user,
            request_id=request_id,
            code="TOOL_DISABLED",
            message="工具已被管理员停用，未调用外部系统。",
            execution=execution,
        )
        return _outcome(
            approval=approval,
            action=action,
            case=case,
            execution=execution,
            message="工具已停用，动作执行失败。",
        )
    kill_switch, kill_reason, _ = await get_kill_switch(db)
    if kill_switch:
        reason = f"：{kill_reason}" if kill_reason else ""
        execution = await _fail_action(
            db,
            action=action,
            case=case,
            user=user,
            request_id=request_id,
            code="KILL_SWITCH_ENABLED",
            message=f"Kill Switch 已开启{reason}，未调用外部系统。",
            execution=execution,
        )
        return _outcome(
            approval=approval,
            action=action,
            case=case,
            execution=execution,
            message="Kill Switch 已开启，动作执行失败。",
        )

    try:
        output, summary = execute_mock_write(
            action.tool_name, dict(action.args), mock_mode
        )
    except ToolRuntimeError as exc:
        execution = await _fail_action(
            db,
            action=action,
            case=case,
            user=user,
            request_id=request_id,
            code=exc.code,
            message=exc.message,
            execution=execution,
        )
        return _outcome(
            approval=approval,
            action=action,
            case=case,
            execution=execution,
            message="工具执行失败，Case 已标记为执行失败。",
        )

    verification = verify_mock_write(action.tool_name, dict(action.args))
    if not verification.get("verified", False):
        execution = await _fail_action(
            db,
            action=action,
            case=case,
            user=user,
            request_id=request_id,
            code="VERIFICATION_FAILED",
            message="工具返回成功，但只读复核未通过。",
            execution=execution,
        )
        execution.output = output
        execution.result_summary = summary
        execution.verification = verification
        await record_event(
            db,
            event_type="action.verification_failed",
            actor_id=user.id,
            actor_role=user.role,
            request_id=request_id,
            case_id=case.id,
            payload={
                "action_id": action.id,
                "execution_id": execution.id,
                "verification": verification,
            },
            result="failed",
        )
        return _outcome(
            approval=approval,
            action=action,
            case=case,
            execution=execution,
            message="执行结果验证失败，Case 已标记为失败。",
        )

    execution = await _finish_execution_success(
        db,
        action=action,
        case=case,
        user=user,
        request_id=request_id,
        execution=execution,
        output=output,
        summary=summary,
        verification=verification,
    )
    return _outcome(
        approval=approval,
        action=action,
        case=case,
        execution=execution,
        message="动作已执行并通过只读复核，Case 已解决。",
    )
