from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import new_id
from app.models.action import ActionRequest, Approval, WorkflowCheckpoint
from app.models.case import Case
from app.schemas.action import CheckpointOut

WORKFLOW_VERSION = 1


async def record_checkpoint(
    db: AsyncSession,
    *,
    case: Case,
    node: str,
    status: str = "complete",
    state: dict[str, Any] | None = None,
    parent_id: str | None = None,
) -> WorkflowCheckpoint:
    max_result = await db.execute(
        select(func.max(WorkflowCheckpoint.sequence)).where(
            WorkflowCheckpoint.case_id == case.id
        )
    )
    sequence = int(max_result.scalar_one_or_none() or 0) + 1
    if parent_id is None:
        latest_result = await db.execute(
            select(WorkflowCheckpoint.id)
            .where(WorkflowCheckpoint.case_id == case.id)
            .order_by(WorkflowCheckpoint.sequence.desc())
            .limit(1)
        )
        parent_id = latest_result.scalar_one_or_none()
    payload = {
        "case_status": case.status,
        "current_node": case.current_node,
        "ticket_id": case.ticket_id,
        "action_id": case.action_id,
        **(state or {}),
    }
    checkpoint = WorkflowCheckpoint(
        id=new_id("ckpt"),
        case_id=case.id,
        thread_id=case.id,
        sequence=sequence,
        parent_id=parent_id,
        node=node,
        status=status,
        workflow_version=WORKFLOW_VERSION,
        state=payload,
    )
    db.add(checkpoint)
    await db.flush()
    return checkpoint


async def latest_checkpoint(
    db: AsyncSession, case_id: str
) -> WorkflowCheckpoint | None:
    result = await db.execute(
        select(WorkflowCheckpoint)
        .where(WorkflowCheckpoint.case_id == case_id)
        .order_by(WorkflowCheckpoint.sequence.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def ensure_await_approval_checkpoint(
    db: AsyncSession,
    *,
    case: Case,
    action: ActionRequest,
    approval: Approval,
) -> WorkflowCheckpoint:
    result = await db.execute(
        select(WorkflowCheckpoint)
        .where(
            WorkflowCheckpoint.case_id == case.id,
            WorkflowCheckpoint.node == "await_approval",
        )
        .order_by(WorkflowCheckpoint.sequence.desc())
        .limit(1)
    )
    checkpoint = result.scalar_one_or_none()
    if checkpoint is not None and checkpoint.state.get("action_id") == action.id:
        return checkpoint

    return await record_checkpoint(
        db,
        case=case,
        node="await_approval",
        status="recovered",
        state={
            "action_id": action.id,
            "action_status": action.status,
            "approval_id": approval.id,
            "approval_status": approval.status,
            "recovered_from_business_state": True,
        },
    )


async def list_checkpoints(db: AsyncSession, case_id: str) -> list[CheckpointOut]:
    result = await db.execute(
        select(WorkflowCheckpoint)
        .where(WorkflowCheckpoint.case_id == case_id)
        .order_by(WorkflowCheckpoint.sequence.asc())
    )
    return [
        CheckpointOut(
            id=item.id,
            case_id=item.case_id,
            thread_id=item.thread_id,
            sequence=item.sequence,
            node=item.node,
            status=item.status,
            workflow_version=item.workflow_version,
            state=dict(item.state or {}),
            created_at=item.created_at,
        )
        for item in result.scalars().all()
    ]
