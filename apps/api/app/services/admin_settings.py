from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.rbac import ROLE_LABELS, ROLE_PERMISSIONS, Role
from app.core.security import new_id, utcnow
from app.models.action import SystemSetting
from app.models.config import PromptVersion
from app.models.user import User
from app.schemas.admin import (
    AdminUserOut,
    AdminUserUpdate,
    PromptVersionCreate,
    PromptVersionOut,
    RuntimeConfig,
    TaxonomyResponse,
)
from app.services.audit import record_event
from app.services.eval_seed import ensure_eval_metadata
from app.services.triage import CATEGORY_LABELS, PRIORITY_LABELS

RUNTIME_CONFIG_KEY = "runtime_config"


async def get_runtime_config(db: AsyncSession) -> RuntimeConfig:
    row = await db.get(SystemSetting, RUNTIME_CONFIG_KEY)
    return RuntimeConfig.model_validate((row.value if row else {}) or {})


async def update_runtime_config(
    db: AsyncSession,
    *,
    payload: RuntimeConfig,
    user: User,
    request_id: str,
) -> RuntimeConfig:
    row = await db.get(SystemSetting, RUNTIME_CONFIG_KEY)
    before = dict(row.value or {}) if row else {}
    if row is None:
        row = SystemSetting(key=RUNTIME_CONFIG_KEY, value=payload.model_dump())
        db.add(row)
    else:
        row.value = payload.model_dump()
        row.updated_at = utcnow()
    await record_event(
        db,
        event_type="config.changed",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        payload={
            "setting": "runtime_config",
            "before": before,
            "after": payload.model_dump(),
        },
    )
    await db.commit()
    return payload


def _prompt_out(prompt: PromptVersion, creator: User | None) -> PromptVersionOut:
    return PromptVersionOut(
        id=prompt.id,
        version=prompt.version,
        name=prompt.name,
        system_prompt=prompt.system_prompt,
        is_active=prompt.is_active,
        created_by_id=prompt.created_by_id,
        created_by_name=creator.name if creator else None,
        created_at=prompt.created_at,
    )


async def list_prompt_versions(
    db: AsyncSession, *, owner_id: str | None = None
) -> list[PromptVersionOut]:
    await ensure_eval_metadata(db, owner_id=owner_id)
    await db.commit()
    result = await db.execute(
        select(PromptVersion).order_by(PromptVersion.created_at.asc())
    )
    prompts = list(result.scalars().all())
    creator_ids = {prompt.created_by_id for prompt in prompts if prompt.created_by_id}
    creators: dict[str, User] = {}
    if creator_ids:
        users = await db.execute(select(User).where(User.id.in_(creator_ids)))
        creators = {user.id: user for user in users.scalars().all()}
    return [_prompt_out(prompt, creators.get(prompt.created_by_id or "")) for prompt in prompts]


async def create_prompt_version(
    db: AsyncSession,
    *,
    payload: PromptVersionCreate,
    user: User,
    request_id: str,
) -> PromptVersionOut:
    existing = await db.execute(
        select(PromptVersion.id).where(PromptVersion.version == payload.version)
    )
    if existing.scalar_one_or_none() is not None:
        raise AppError("CONFLICT", "Prompt 版本已存在", 409)
    if payload.activate:
        await db.execute(update(PromptVersion).values(is_active=False))
    prompt = PromptVersion(
        id=new_id("prompt"),
        version=payload.version,
        name=payload.name,
        system_prompt=payload.system_prompt,
        is_active=payload.activate,
        created_by_id=user.id,
    )
    db.add(prompt)
    await record_event(
        db,
        event_type="config.changed",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        payload={
            "setting": "prompt_version",
            "version": payload.version,
            "name": payload.name,
            "activated": payload.activate,
        },
    )
    await db.commit()
    await db.refresh(prompt)
    return _prompt_out(prompt, user)


async def activate_prompt_version(
    db: AsyncSession,
    *,
    prompt_id: str,
    user: User,
    request_id: str,
) -> PromptVersionOut:
    prompt = await db.get(PromptVersion, prompt_id)
    if prompt is None:
        raise AppError("NOT_FOUND", "Prompt 版本不存在", 404)
    previous = list(
        (
            await db.execute(
                select(PromptVersion.version).where(PromptVersion.is_active.is_(True))
            )
        ).scalars().all()
    )
    await db.execute(update(PromptVersion).values(is_active=False))
    prompt.is_active = True
    await record_event(
        db,
        event_type="config.changed",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        payload={
            "setting": "active_prompt_version",
            "before": previous,
            "after": prompt.version,
        },
    )
    await db.commit()
    await db.refresh(prompt)
    return _prompt_out(prompt, user)


def _admin_user_out(user: User) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        role_label=ROLE_LABELS.get(user.role, user.role),
        department=user.department,
        is_active=user.is_active,
        created_at=user.created_at,
    )


async def list_admin_users(db: AsyncSession) -> list[AdminUserOut]:
    result = await db.execute(select(User).order_by(User.created_at.asc(), User.name.asc()))
    return [_admin_user_out(user) for user in result.scalars().all()]


async def update_admin_user(
    db: AsyncSession,
    *,
    target_id: str,
    payload: AdminUserUpdate,
    user: User,
    request_id: str,
) -> AdminUserOut:
    target = await db.get(User, target_id)
    if target is None:
        raise AppError("NOT_FOUND", "用户不存在", 404)
    next_role = payload.role or target.role
    next_active = target.is_active if payload.is_active is None else payload.is_active
    if target.id == user.id and (next_role != user.role or not next_active):
        raise AppError("INVALID_STATE", "不能停用自己或修改自己的管理员角色", 409)
    if target.role == Role.ADMIN.value and (
        next_role != Role.ADMIN.value or not next_active
    ):
        count_result = await db.execute(
            select(func.count(User.id)).where(
                User.role == Role.ADMIN.value,
                User.is_active.is_(True),
                User.id != target.id,
            )
        )
        if int(count_result.scalar_one()) == 0:
            raise AppError("INVALID_STATE", "必须保留至少一名启用状态的管理员", 409)
    before = {
        "role": target.role,
        "department": target.department,
        "is_active": target.is_active,
    }
    target.role = next_role
    if payload.department is not None:
        target.department = payload.department.strip()
    target.is_active = next_active
    target.updated_at = utcnow()
    await record_event(
        db,
        event_type="config.changed",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        payload={
            "setting": "user",
            "target_user_id": target.id,
            "before": before,
            "after": {
                "role": target.role,
                "department": target.department,
                "is_active": target.is_active,
            },
        },
    )
    await db.commit()
    await db.refresh(target)
    return _admin_user_out(target)


def get_taxonomy() -> TaxonomyResponse:
    roles: list[dict[str, Any]] = []
    for role in Role:
        roles.append(
            {
                "key": role.value,
                "label": ROLE_LABELS.get(role, role.value),
                "permissions": sorted(ROLE_PERMISSIONS.get(role, frozenset())),
            }
        )
    return TaxonomyResponse(
        categories=[
            {"key": key, "label": label} for key, label in CATEGORY_LABELS.items()
        ],
        priorities=[
            {"key": key, "label": label} for key, label in PRIORITY_LABELS.items()
        ],
        roles=roles,
    )
