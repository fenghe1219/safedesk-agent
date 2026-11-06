from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import new_id, utcnow
from app.models.feedback import MessageFeedback
from app.models.message import Message
from app.models.user import User
from app.schemas.feedback import FeedbackCreate, FeedbackOut
from app.services.audit import record_event
from app.services.case_service import get_accessible_case


def _out(row: MessageFeedback) -> FeedbackOut:
    return FeedbackOut(
        id=row.id,
        message_id=row.message_id,
        user_id=row.user_id,
        rating=row.rating,
        reason=row.reason,
        comment=row.comment,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def submit_feedback(
    db: AsyncSession,
    *,
    message_id: str,
    payload: FeedbackCreate,
    user: User,
    request_id: str,
) -> FeedbackOut:
    message = await db.get(Message, message_id)
    if message is None or message.role != "assistant":
        raise AppError("NOT_FOUND", "助手消息不存在", 404)
    case = await get_accessible_case(db, user, message.case_id)
    if payload.rating == "helpful":
        reason = None
    else:
        reason = payload.reason or "other"
    result = await db.execute(
        select(MessageFeedback).where(
            MessageFeedback.message_id == message.id,
            MessageFeedback.user_id == user.id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = MessageFeedback(
            id=new_id("msgfb"),
            message_id=message.id,
            user_id=user.id,
            rating=payload.rating,
            reason=reason,
            comment=payload.comment.strip(),
        )
        db.add(row)
    else:
        row.rating = payload.rating
        row.reason = reason
        row.comment = payload.comment.strip()
        row.updated_at = utcnow()
    await record_event(
        db,
        event_type="feedback.submitted",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        case_id=case.id,
        payload={
            "message_id": message.id,
            "rating": payload.rating,
            "reason": reason,
            "candidate_only": True,
        },
    )
    await db.commit()
    await db.refresh(row)
    return _out(row)
