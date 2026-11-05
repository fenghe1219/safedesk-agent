from fastapi import APIRouter, Depends, Request

from app.api.deps import get_current_session
from app.core.config import settings
from app.models.session import UserSession
from app.schemas.common import MeResponse
from app.services.auth_service import build_me

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeResponse)
async def me(request: Request, session: UserSession = Depends(get_current_session)) -> MeResponse:
    csrf_token = request.cookies.get(settings.csrf_cookie_name, "")
    return build_me(session.user, csrf_token)
