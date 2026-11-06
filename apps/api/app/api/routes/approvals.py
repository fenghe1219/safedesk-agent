from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import request_id, require_csrf, require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.action import (
    ActionDecisionResponse,
    ApprovalDetailOut,
    ApprovalListResponse,
    ApprovalStatus,
    ApproveRequest,
    CaseActionOut,
    CheckpointListResponse,
    RejectRequest,
)
from app.services.action_service import (
    _decision_response,
    approve_action,
    expire_stale_approvals,
    get_approval_detail,
    get_case_action,
    list_approvals,
    reject_action,
)
from app.services.case_service import get_accessible_case
from app.services.workflow import list_checkpoints

router = APIRouter(prefix="/approvals", tags=["approvals"])
case_router = APIRouter(prefix="/cases", tags=["approvals"])


@router.get("", response_model=ApprovalListResponse)
async def get_approvals(
    status: ApprovalStatus | None = Query(default=None),
    user: User = Depends(require_permission("approval:view")),
    db: AsyncSession = Depends(get_db),
) -> ApprovalListResponse:
    if await expire_stale_approvals(db):
        await db.commit()
    return ApprovalListResponse(
        items=await list_approvals(db, user=user, status=status)
    )


@router.get("/{approval_id}", response_model=ApprovalDetailOut)
async def get_approval(
    approval_id: str,
    user: User = Depends(require_permission("approval:view")),
    db: AsyncSession = Depends(get_db),
) -> ApprovalDetailOut:
    if await expire_stale_approvals(db):
        await db.commit()
    return await get_approval_detail(db, user=user, approval_id=approval_id)


@router.post("/{approval_id}/approve", response_model=ActionDecisionResponse)
async def post_approve(
    approval_id: str,
    payload: ApproveRequest,
    request: Request,
    user: User = Depends(require_permission("approval:decide")),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> ActionDecisionResponse:
    if await expire_stale_approvals(db, request_id=request_id(request)):
        await db.commit()
    outcome = await approve_action(
        db,
        approval_id=approval_id,
        user=user,
        expected_args_hash=payload.expected_args_hash,
        approval_version=payload.approval_version,
        reason=payload.reason,
        request_id=request_id(request),
    )
    await db.commit()
    return await _decision_response(db, outcome)


@router.post("/{approval_id}/reject", response_model=ActionDecisionResponse)
async def post_reject(
    approval_id: str,
    payload: RejectRequest,
    request: Request,
    user: User = Depends(require_permission("approval:decide")),
    _: None = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> ActionDecisionResponse:
    if await expire_stale_approvals(db, request_id=request_id(request)):
        await db.commit()
    outcome = await reject_action(
        db,
        approval_id=approval_id,
        user=user,
        approval_version=payload.approval_version,
        reason=payload.reason.strip(),
        request_id=request_id(request),
    )
    await db.commit()
    return await _decision_response(db, outcome)


@case_router.get("/{case_id}/action", response_model=CaseActionOut)
async def get_case_action_route(
    case_id: str,
    user: User = Depends(require_permission("case:read")),
    db: AsyncSession = Depends(get_db),
) -> CaseActionOut:
    await get_accessible_case(db, user, case_id)
    if await expire_stale_approvals(db):
        await db.commit()
    result = await get_case_action(db, user=user, case_id=case_id)
    await db.commit()
    return result


@case_router.get("/{case_id}/checkpoints", response_model=CheckpointListResponse)
async def get_case_checkpoints(
    case_id: str,
    user: User = Depends(require_permission("case:read")),
    db: AsyncSession = Depends(get_db),
) -> CheckpointListResponse:
    case = await get_accessible_case(db, user, case_id)
    return CheckpointListResponse(items=await list_checkpoints(db, case.id))
