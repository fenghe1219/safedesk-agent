from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import request_id, require_csrf, require_permission
from app.db.session import get_db
from app.models.action import ToolPolicy
from app.models.user import User
from app.schemas.action import (
    KillSwitchOut,
    KillSwitchUpdate,
    ToolPolicyListResponse,
    ToolPolicyOut,
    ToolPolicyUpdate,
)
from app.services.audit import record_event
from app.services.tools import (
    TOOL_ORDER,
    get_kill_switch,
    get_tool_spec,
    list_policy_rows,
    set_kill_switch,
    set_tool_policy,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _policy_out(tool_name: str, row: ToolPolicy | None) -> ToolPolicyOut:
    spec = get_tool_spec(tool_name)
    return ToolPolicyOut(
        name=spec.name,
        label=spec.label,
        tool_type=spec.tool_type,
        risk_level=spec.risk_level,
        description=spec.description,
        requires_approval=spec.requires_approval,
        timeout_seconds=spec.timeout_seconds,
        enabled=row.enabled if row else True,
        mock_mode=row.mock_mode if row else "success",
    )


@router.get("/tools", response_model=ToolPolicyListResponse)
async def get_tools(
    _: User = Depends(require_permission("settings:manage")),
    db: AsyncSession = Depends(get_db),
) -> ToolPolicyListResponse:
    rows = await list_policy_rows(db)
    kill_switch, reason, _ = await get_kill_switch(db)
    return ToolPolicyListResponse(
        items=[_policy_out(name, rows.get(name)) for name in TOOL_ORDER],
        kill_switch_enabled=kill_switch,
        kill_switch_reason=reason,
    )


@router.patch("/tools/{tool_name}", response_model=ToolPolicyOut)
async def patch_tool(
    tool_name: str,
    payload: ToolPolicyUpdate,
    request: Request,
    user: User = Depends(require_permission("settings:manage")),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> ToolPolicyOut:
    spec = get_tool_spec(tool_name)
    row = await set_tool_policy(
        db,
        spec.name,
        enabled=payload.enabled,
        mock_mode=payload.mock_mode,
    )
    await db.flush()
    await record_event(
        db,
        event_type="config.changed",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id(request),
        payload={
            "setting": "tool_policy",
            "tool_name": spec.name,
            "enabled": row.enabled,
            "mock_mode": row.mock_mode,
        },
    )
    await db.commit()
    return _policy_out(spec.name, row)


@router.get("/kill-switch", response_model=KillSwitchOut)
async def get_kill_switch_route(
    _: User = Depends(require_permission("settings:manage")),
    db: AsyncSession = Depends(get_db),
) -> KillSwitchOut:
    enabled, reason, updated_at = await get_kill_switch(db)
    return KillSwitchOut(enabled=enabled, reason=reason, updated_at=updated_at)


@router.put("/kill-switch", response_model=KillSwitchOut)
async def put_kill_switch(
    payload: KillSwitchUpdate,
    request: Request,
    user: User = Depends(require_permission("settings:manage")),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> KillSwitchOut:
    row = await set_kill_switch(
        db, enabled=payload.enabled, reason=payload.reason
    )
    await db.flush()
    await record_event(
        db,
        event_type="config.changed",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id(request),
        payload={
            "setting": "kill_switch",
            "enabled": payload.enabled,
            "reason": payload.reason,
        },
    )
    await db.commit()
    return KillSwitchOut(
        enabled=payload.enabled, reason=payload.reason, updated_at=row.updated_at
    )
