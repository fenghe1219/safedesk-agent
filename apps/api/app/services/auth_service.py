from datetime import datetime, timedelta

from fastapi import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rbac import (
    ROLE_LABELS,
    Role,
    default_path_for,
    navigation_for,
    permissions_for,
)
from app.core.security import hash_token, new_id, new_token, utcnow
from app.models.session import UserSession
from app.models.user import User
from app.schemas.common import MeResponse, NavItem, UserOut


def build_me(user: User, csrf_token: str) -> MeResponse:
    return MeResponse(
        user=UserOut(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,
            role_label=ROLE_LABELS.get(user.role, user.role),
            department=user.department,
        ),
        permissions=permissions_for(user.role),
        navigation=[NavItem(**item) for item in navigation_for(user.role)],
        demo_mode=settings.demo_mode,
        csrf_token=csrf_token,
        default_path=default_path_for(user.role),
    )


async def find_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower().strip()))
    return result.scalar_one_or_none()


async def find_user_by_role(db: AsyncSession, role: Role) -> User | None:
    result = await db.execute(
        select(User).where(User.role == role.value, User.is_active.is_(True)).limit(1)
    )
    return result.scalar_one_or_none()


async def create_session(
    db: AsyncSession, user: User
) -> tuple[str, str, datetime]:
    raw_token = new_token()
    csrf_token = new_token(24)
    expires_at = utcnow() + timedelta(hours=settings.session_ttl_hours)
    session = UserSession(
        id=new_id("sess"),
        user_id=user.id,
        token_hash=hash_token(raw_token),
        csrf_token=hash_token(csrf_token),
        expires_at=expires_at,
    )
    db.add(session)
    await db.flush()
    return raw_token, csrf_token, expires_at


def apply_session_cookies(
    response: Response, raw_token: str, csrf_token: str, expires_at: datetime
) -> None:
    max_age = max(0, int((expires_at - utcnow()).total_seconds()))
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=max_age,
        path="/",
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=max_age,
        path="/",
    )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")


async def revoke_session(db: AsyncSession, session: UserSession) -> None:
    await db.delete(session)
