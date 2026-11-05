from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_session, request_id, require_csrf
from app.core.config import settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models.session import UserSession
from app.schemas.auth import SwitchUserRequest
from app.schemas.common import MeResponse
from app.services.audit import record_event
from app.services.auth_service import (
    apply_session_cookies,
    build_me,
    create_session,
    find_user_by_role,
    revoke_session,
)

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/switch-user", response_model=MeResponse)
async def switch_user(
    payload: SwitchUserRequest,
    request: Request,
    response: Response,
    session: UserSession = Depends(get_current_session),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    if not settings.demo_mode:
        raise AppError("NOT_FOUND", "演示模式未启用", 404)

    target = await find_user_by_role(db, payload.role)
    if target is None:
        raise AppError("NOT_FOUND", "没有可用的演示账号", 404)

    await record_event(
        db,
        event_type="auth.demo_switch",
        actor_id=session.user_id,
        actor_role=session.user.role,
        request_id=request_id(request),
        payload={"target_role": payload.role.value, "target_user_id": target.id},
    )
    await revoke_session(db, session)
    raw_token, csrf_token, expires_at = await create_session(db, target)
    await db.commit()
    apply_session_cookies(response, raw_token, csrf_token, expires_at)
    return build_me(target, csrf_token)
