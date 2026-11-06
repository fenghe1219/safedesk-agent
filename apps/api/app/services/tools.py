from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import new_id, utcnow
from app.models.action import SystemSetting, ToolPolicy
from app.models.case import Case
from app.models.user import User
from app.services.audit import record_event

ToolType = Literal["READ", "WRITE"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]
MockMode = Literal["success", "fail", "timeout"]

KILL_SWITCH_KEY = "kill_switch"


class UserToolArgs(BaseModel):
    user_id: str = Field(min_length=1, max_length=40)


class VpnStatusArgs(UserToolArgs):
    pass


class ResetVpnCertificateArgs(UserToolArgs):
    reason: str = Field(min_length=1, max_length=300)


class GrantAppAccessArgs(UserToolArgs):
    app_name: str = Field(min_length=1, max_length=80)
    role: str = Field(default="user", min_length=1, max_length=40)
    expires_in_days: int = Field(default=30, ge=1, le=90)
    reason: str = Field(min_length=1, max_length=300)


class AccountStatusArgs(UserToolArgs):
    pass


class ServiceHealthArgs(BaseModel):
    service: str = Field(min_length=1, max_length=80)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    label: str
    tool_type: ToolType
    risk_level: RiskLevel
    description: str
    args_model: type[BaseModel]
    requires_approval: bool
    timeout_seconds: int = 5
    verification_tool: str | None = None


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "get_vpn_status": ToolSpec(
        name="get_vpn_status",
        label="查询 VPN 证书状态",
        tool_type="READ",
        risk_level="LOW",
        description="查询当前用户的 VPN 账号与证书状态。",
        args_model=VpnStatusArgs,
        requires_approval=False,
        timeout_seconds=3,
    ),
    "get_account_status": ToolSpec(
        name="get_account_status",
        label="查询账号状态",
        tool_type="READ",
        risk_level="LOW",
        description="查询账号是否锁定、启用及多因素认证状态。",
        args_model=AccountStatusArgs,
        requires_approval=False,
        timeout_seconds=3,
    ),
    "get_service_health": ToolSpec(
        name="get_service_health",
        label="查询服务健康状态",
        tool_type="READ",
        risk_level="LOW",
        description="查询指定内部系统的当前服务状态。",
        args_model=ServiceHealthArgs,
        requires_approval=False,
        timeout_seconds=3,
    ),
    "reset_vpn_certificate": ToolSpec(
        name="reset_vpn_certificate",
        label="重置 VPN 证书",
        tool_type="WRITE",
        risk_level="HIGH",
        description="为当前用户重新签发 VPN 证书，仅影响该用户。",
        args_model=ResetVpnCertificateArgs,
        requires_approval=True,
        timeout_seconds=10,
        verification_tool="get_vpn_status",
    ),
    "grant_app_access": ToolSpec(
        name="grant_app_access",
        label="授予应用访问权限",
        tool_type="WRITE",
        risk_level="HIGH",
        description="为当前用户授予指定应用角色和有效期。",
        args_model=GrantAppAccessArgs,
        requires_approval=True,
        timeout_seconds=10,
        verification_tool="get_account_status",
    ),
}

TOOL_ORDER = tuple(TOOL_REGISTRY)


class ToolRuntimeError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ReadToolResult:
    audit_id: str
    tool_name: str
    tool_label: str
    output: dict[str, Any]
    summary: str

    @property
    def evidence_id(self) -> str:
        return f"toolcall:{self.audit_id}"


def get_tool_spec(tool_name: str) -> ToolSpec:
    spec = TOOL_REGISTRY.get(tool_name)
    if spec is None:
        raise AppError("NOT_FOUND", "工具未注册", 404)
    return spec


def validate_tool_args(tool_name: str, raw_args: dict[str, Any]) -> dict[str, Any]:
    spec = get_tool_spec(tool_name)
    try:
        return spec.args_model.model_validate(raw_args).model_dump()
    except ValidationError as exc:
        raise AppError(
            "VALIDATION_ERROR",
            "工具参数未通过校验",
            422,
            {"tool_name": tool_name, "issues": exc.errors(include_url=False)},
        ) from exc


def canonical_args_hash(tool_name: str, args: dict[str, Any]) -> str:
    payload = json.dumps(
        {"tool_name": tool_name, "args": args},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


async def get_tool_policy(db: AsyncSession, tool_name: str) -> tuple[bool, str]:
    get_tool_spec(tool_name)
    row = await db.get(ToolPolicy, tool_name)
    if row is None:
        return True, "success"
    return row.enabled, row.mock_mode


async def set_tool_policy(
    db: AsyncSession,
    tool_name: str,
    *,
    enabled: bool | None,
    mock_mode: str | None,
) -> ToolPolicy:
    get_tool_spec(tool_name)
    row = await db.get(ToolPolicy, tool_name)
    if row is None:
        row = ToolPolicy(name=tool_name, enabled=True, mock_mode="success")
        db.add(row)
    if enabled is not None:
        row.enabled = enabled
    if mock_mode is not None:
        if mock_mode not in {"success", "fail", "timeout"}:
            raise AppError("VALIDATION_ERROR", "Mock 模式不合法", 422)
        row.mock_mode = mock_mode
    row.updated_at = utcnow()
    return row


async def get_kill_switch(db: AsyncSession) -> tuple[bool, str | None, Any]:
    row = await db.get(SystemSetting, KILL_SWITCH_KEY)
    if row is None:
        return False, None, None
    value = row.value or {}
    return bool(value.get("enabled")), value.get("reason"), row.updated_at


async def set_kill_switch(
    db: AsyncSession, *, enabled: bool, reason: str | None
) -> SystemSetting:
    row = await db.get(SystemSetting, KILL_SWITCH_KEY)
    if row is None:
        row = SystemSetting(key=KILL_SWITCH_KEY, value={})
        db.add(row)
    row.value = {"enabled": enabled, "reason": reason}
    row.updated_at = utcnow()
    return row


async def call_read_tool(
    db: AsyncSession,
    *,
    tool_name: str,
    raw_args: dict[str, Any],
    user: User,
    case: Case,
    request_id: str,
) -> ReadToolResult:
    spec = get_tool_spec(tool_name)
    if spec.tool_type != "READ":
        raise AppError("FORBIDDEN", "写工具不能通过只读通道执行", 403)
    enabled, mock_mode = await get_tool_policy(db, tool_name)
    if not enabled:
        raise AppError("TOOL_DISABLED", f"工具 {spec.label} 已被管理员停用", 409)
    args = validate_tool_args(tool_name, raw_args)
    if mock_mode == "fail":
        await record_event(
            db,
            event_type="tool.read_failed",
            actor_id=user.id,
            actor_role=user.role,
            request_id=request_id,
            case_id=case.id,
            payload={"tool_name": tool_name, "args": args, "error_code": "TOOL_FAILED"},
            result="failed",
        )
        raise AppError("TOOL_FAILED", "只读工具执行失败", 502)
    if mock_mode == "timeout":
        await record_event(
            db,
            event_type="tool.read_failed",
            actor_id=user.id,
            actor_role=user.role,
            request_id=request_id,
            case_id=case.id,
            payload={"tool_name": tool_name, "args": args, "error_code": "TOOL_TIMEOUT"},
            result="failed",
        )
        raise AppError("TOOL_TIMEOUT", "只读工具执行超时", 504)

    output = _read_output(tool_name, args)
    summary = _read_summary(tool_name, output)
    audit = await record_event(
        db,
        event_type="tool.read_executed",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=case.id,
        payload={
            "tool_name": tool_name,
            "tool_label": spec.label,
            "args": args,
            "result_summary": summary,
            "mock": True,
        },
    )
    await db.flush()
    return ReadToolResult(
        audit_id=audit.id,
        tool_name=tool_name,
        tool_label=spec.label,
        output=output,
        summary=summary,
    )


def execute_mock_write(
    tool_name: str, args: dict[str, Any], mock_mode: str
) -> tuple[dict[str, Any], str]:
    get_tool_spec(tool_name)
    if mock_mode == "fail":
        raise ToolRuntimeError("TOOL_FAILED", "模拟工具返回执行失败")
    if mock_mode == "timeout":
        raise ToolRuntimeError("TOOL_TIMEOUT", "模拟工具执行超时")
    if tool_name == "reset_vpn_certificate":
        output = {
            "reset": True,
            "certificate_status": "ACTIVE",
            "reference": f"vpn-reset-{new_id('ref')[-8:]}",
        }
        return output, "已重置当前用户 VPN 证书，并收到重新签发回执。"
    if tool_name == "grant_app_access":
        output = {
            "granted": True,
            "app_name": args["app_name"],
            "role": args["role"],
            "expires_in_days": args["expires_in_days"],
            "reference": f"access-{new_id('ref')[-8:]}",
        }
        return output, f"已授予 {args['app_name']} 的 {args['role']} 权限。"
    raise ToolRuntimeError("TOOL_FAILED", "工具没有可用的写连接器")


def verify_mock_write(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "reset_vpn_certificate":
        return {
            "verified": True,
            "tool_name": "get_vpn_status",
            "status": "ACTIVE",
            "summary": "只读复核显示 VPN 证书状态为 ACTIVE。",
        }
    if tool_name == "grant_app_access":
        return {
            "verified": True,
            "tool_name": "get_account_status",
            "status": "GRANTED",
            "app_name": args["app_name"],
            "summary": f"只读复核显示 {args['app_name']} 访问权限已生效。",
        }
    return {"verified": False, "summary": "没有可用的只读验证工具。"}


def _read_output(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "get_vpn_status":
        return {
            "user_id": args["user_id"],
            "status": "EXPIRED",
            "account_enabled": True,
            "certificate_expires_at": (utcnow() - timedelta(days=1)).isoformat(),
            "mock": True,
        }
    if tool_name == "get_account_status":
        return {
            "user_id": args["user_id"],
            "enabled": True,
            "locked": False,
            "mfa_enabled": True,
            "mock": True,
        }
    if tool_name == "get_service_health":
        return {"service": args["service"], "status": "operational", "mock": True}
    return {"mock": True}


def _read_summary(tool_name: str, output: dict[str, Any]) -> str:
    if tool_name == "get_vpn_status":
        return "只读检查显示 VPN 证书已过期，账号本身处于启用状态。"
    if tool_name == "get_account_status":
        return "只读检查显示账号已启用、未锁定，且已开启多因素认证。"
    if tool_name == "get_service_health":
        return f"只读检查显示 {output.get('service', '目标系统')} 当前运行正常。"
    return "只读工具执行完成。"


async def list_policy_rows(db: AsyncSession) -> dict[str, ToolPolicy]:
    result = await db.execute(select(ToolPolicy))
    return {row.name: row for row in result.scalars().all()}
