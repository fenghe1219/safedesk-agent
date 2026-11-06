from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import request_id, require_csrf, require_permission
from app.core.errors import AppError
from app.db.session import get_db
from app.models.user import User
from app.schemas.admin import (
    AdminSettingsResponse,
    AdminUserListResponse,
    AdminUserOut,
    AdminUserUpdate,
    DemoResetRequest,
    DemoResetResponse,
    PromptVersionCreate,
    PromptVersionListResponse,
    PromptVersionOut,
    RuntimeConfig,
    TaxonomyResponse,
)
from app.services.admin_settings import (
    activate_prompt_version,
    create_prompt_version,
    get_runtime_config,
    get_taxonomy,
    list_admin_users,
    list_prompt_versions,
    update_admin_user,
    update_runtime_config,
)
from app.services.demo_reset import reset_demo_data

router = APIRouter(prefix="/admin", tags=["admin-settings"])


@router.get("/settings", response_model=AdminSettingsResponse)
async def get_settings_summary(
    user: User = Depends(require_permission("settings:manage")),
    db: AsyncSession = Depends(get_db),
) -> AdminSettingsResponse:
    return AdminSettingsResponse(
        runtime_config=await get_runtime_config(db),
        prompts=await list_prompt_versions(db, owner_id=user.id),
        taxonomy=get_taxonomy(),
        users=await list_admin_users(db),
    )


@router.get("/users", response_model=AdminUserListResponse)
async def get_users(
    _: User = Depends(require_permission("settings:manage")),
    db: AsyncSession = Depends(get_db),
) -> AdminUserListResponse:
    return AdminUserListResponse(items=await list_admin_users(db))


@router.patch("/users/{user_id}", response_model=AdminUserOut)
async def patch_user(
    user_id: str,
    payload: AdminUserUpdate,
    request: Request,
    user: User = Depends(require_permission("settings:manage")),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> AdminUserOut:
    return await update_admin_user(
        db,
        target_id=user_id,
        payload=payload,
        user=user,
        request_id=request_id(request),
    )


@router.get("/runtime-config", response_model=RuntimeConfig)
async def get_runtime(
    _: User = Depends(require_permission("settings:manage")),
    db: AsyncSession = Depends(get_db),
) -> RuntimeConfig:
    return await get_runtime_config(db)


@router.put("/runtime-config", response_model=RuntimeConfig)
async def put_runtime(
    payload: RuntimeConfig,
    request: Request,
    user: User = Depends(require_permission("settings:manage")),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> RuntimeConfig:
    return await update_runtime_config(
        db, payload=payload, user=user, request_id=request_id(request)
    )


@router.get("/prompts", response_model=PromptVersionListResponse)
async def get_prompts(
    user: User = Depends(require_permission("settings:manage")),
    db: AsyncSession = Depends(get_db),
) -> PromptVersionListResponse:
    return PromptVersionListResponse(
        items=await list_prompt_versions(db, owner_id=user.id)
    )


@router.post("/prompts", response_model=PromptVersionOut, status_code=201)
async def post_prompt(
    payload: PromptVersionCreate,
    request: Request,
    user: User = Depends(require_permission("settings:manage")),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> PromptVersionOut:
    return await create_prompt_version(
        db, payload=payload, user=user, request_id=request_id(request)
    )


@router.post("/prompts/{prompt_id}/activate", response_model=PromptVersionOut)
async def activate_prompt(
    prompt_id: str,
    request: Request,
    user: User = Depends(require_permission("settings:manage")),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> PromptVersionOut:
    return await activate_prompt_version(
        db, prompt_id=prompt_id, user=user, request_id=request_id(request)
    )


@router.get("/taxonomy", response_model=TaxonomyResponse)
async def taxonomy(
    _: User = Depends(require_permission("settings:manage")),
) -> TaxonomyResponse:
    return get_taxonomy()


@router.post("/reset-demo", response_model=DemoResetResponse)
async def reset_demo(
    payload: DemoResetRequest,
    request: Request,
    user: User = Depends(require_permission("settings:manage")),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> DemoResetResponse:
    if payload.confirmation.strip() != "RESET-DEMO":
        raise AppError("CONFIRMATION_REQUIRED", "请输入 RESET-DEMO 以确认重置", 422)
    return await reset_demo_data(db, user=user, request_id=request_id(request))
