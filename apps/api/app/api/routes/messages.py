import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import request_id, require_csrf, require_permission
from app.core.errors import AppError
from app.db.session import get_db
from app.models.user import User
from app.schemas.message import MessageCreate, MessageListResponse
from app.services.case_service import get_accessible_case
from app.services.conversation import encode_sse, list_case_messages, process_message

router = APIRouter(prefix="/cases", tags=["messages"])


@router.get("/{case_id}/messages", response_model=MessageListResponse)
async def get_messages(
    case_id: str,
    user: User = Depends(require_permission("case:read")),
    db: AsyncSession = Depends(get_db),
) -> MessageListResponse:
    await get_accessible_case(db, user, case_id)
    return MessageListResponse(items=await list_case_messages(db, case_id))


@router.post("/{case_id}/messages")
async def send_message(
    case_id: str,
    payload: MessageCreate,
    request: Request,
    user: User = Depends(require_permission("case:read")),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    case = await get_accessible_case(db, user, case_id)
    if case.status == "CANCELLED":
        raise AppError("INVALID_STATE", "Case 已关闭，请先重新打开", 409)
    content = payload.content.strip()
    if not content:
        raise AppError("VALIDATION_ERROR", "消息不能为空", 422)

    exchange = await process_message(
        db,
        case=case,
        user=user,
        content=content,
        request_id=request_id(request),
        client_message_id=payload.client_message_id,
    )
    body = encode_sse(exchange.events)

    async def stream():
        for line in body.splitlines(keepends=True):
            yield line
            await asyncio.sleep(0.006)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
