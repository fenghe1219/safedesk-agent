from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_session, request_id, require_csrf
from app.core.errors import AppError
from app.core.security import verify_password
from app.db.session import get_db
from app.models.session import UserSession
from app.schemas.auth import LoginRequest
from app.schemas.common import MeResponse
from app.services.audit import record_event
from app.services.auth_service import (
    apply_session_cookies,
    build_me,
    clear_session_cookies,
    create_session,
    find_user_by_email,
    revoke_session,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=MeResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    user = await find_user_by_email(db, payload.email)
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise AppError("UNAUTHENTICATED", "邮箱或密码不正确", 401)

    raw_token, csrf_token, expires_at = await create_session(db, user)
    await record_event(
        db,
        event_type="auth.login",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id(request),
    )
    await db.commit()
    apply_session_cookies(response, raw_token, csrf_token, expires_at)
    return build_me(user, csrf_token)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    session: UserSession = Depends(get_current_session),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await record_event(
        db,
        event_type="auth.logout",
        actor_id=session.user_id,
        actor_role=session.user.role,
        request_id=request_id(request),
    )
    await revoke_session(db, session)
    await db.commit()
    response = Response(status_code=204)
    clear_session_cookies(response)
    return response
