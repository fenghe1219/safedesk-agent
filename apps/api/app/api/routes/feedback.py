from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import request_id, require_csrf, require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.feedback import FeedbackCreate, FeedbackOut
from app.services.feedback import submit_feedback

router = APIRouter(prefix="/messages", tags=["feedback"])


@router.post("/{message_id}/feedback", response_model=FeedbackOut)
async def create_feedback(
    message_id: str,
    payload: FeedbackCreate,
    request: Request,
    user: User = Depends(require_permission("case:read")),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> FeedbackOut:
    return await submit_feedback(
        db,
        message_id=message_id,
        payload=payload,
        user=user,
        request_id=request_id(request),
    )
