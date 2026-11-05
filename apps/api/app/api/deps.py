import secrets
from collections.abc import Awaitable, Callable

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import AppError
from app.core.rbac import has_permission
from app.core.security import as_utc, hash_token, utcnow
from app.db.session import get_db
from app.models.session import UserSession
from app.models.user import User


async def get_current_session(
    request: Request, db: AsyncSession = Depends(get_db)
) -> UserSession:
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise AppError("UNAUTHENTICATED", "请先登录", 401)

    result = await db.execute(
        select(UserSession)
        .options(selectinload(UserSession.user))
        .where(UserSession.token_hash == hash_token(raw_token))
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise AppError("UNAUTHENTICATED", "会话已失效，请重新登录", 401)
    if as_utc(session.expires_at) <= utcnow():
        raise AppError("UNAUTHENTICATED", "会话已过期，请重新登录", 401)
    if not session.user.is_active:
        raise AppError("UNAUTHENTICATED", "账号已停用", 401)
    return session


async def get_current_user(session: UserSession = Depends(get_current_session)) -> User:
    return session.user


async def require_csrf(
    request: Request, session: UserSession = Depends(get_current_session)
) -> None:
    header_token = request.headers.get("X-CSRF-Token", "")
    cookie_token = request.cookies.get(settings.csrf_cookie_name, "")
    if (
        not header_token
        or not cookie_token
        or not secrets.compare_digest(header_token, cookie_token)
        or not secrets.compare_digest(hash_token(cookie_token), session.csrf_token)
    ):
        raise AppError("FORBIDDEN", "CSRF 校验失败，请刷新页面后重试", 403)


def require_permission(permission: str) -> Callable[..., Awaitable[User]]:
    async def dependency(user: User = Depends(get_current_user)) -> User:
        if not has_permission(user.role, permission):
            raise AppError("FORBIDDEN", "当前角色没有该操作权限", 403)
        return user

    return dependency


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "req_unknown")
