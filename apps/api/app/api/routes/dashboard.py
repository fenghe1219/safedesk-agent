from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard import build_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
async def dashboard(
    range_key: Literal["7d", "30d"] = Query(default="30d", alias="range"),
    _: User = Depends(require_permission("dashboard:view")),
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    return await build_dashboard(db, range_key=range_key)
