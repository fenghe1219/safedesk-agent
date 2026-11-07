from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import request_id, require_csrf, require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.memory import MemoryDeleteResponse, MemoryEntryOut, MemoryListResponse
from app.services.memory import delete_memory_entry, list_memory_entries, memory_payload

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("", response_model=MemoryListResponse)
async def list_memory(
    case_id: str | None = Query(default=None),
    include_user: bool = Query(default=True),
    user: User = Depends(require_permission("case:read")),
    db: AsyncSession = Depends(get_db),
) -> MemoryListResponse:
    entries = await list_memory_entries(
        db, user_id=user.id, case_id=case_id, include_user=include_user
    )
    return MemoryListResponse(
        items=[MemoryEntryOut(**memory_payload(entry)) for entry in entries]
    )


@router.delete("/{entry_id}", response_model=MemoryDeleteResponse)
async def delete_memory(
    entry_id: str,
    request: Request,
    user: User = Depends(require_permission("case:read")),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> MemoryDeleteResponse:
    await delete_memory_entry(
        db, entry_id=entry_id, user=user, request_id=request_id(request)
    )
    return MemoryDeleteResponse(deleted=True, entry_id=entry_id)
