from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import utcnow
from app.models.action import (
    ActionRequest,
    Approval,
    SystemSetting,
    ToolExecution,
    ToolPolicy,
    WorkflowCheckpoint,
)
from app.models.case import Case
from app.models.config import PromptVersion
from app.models.eval import EvalDataset, EvalItem, EvalResult, EvalRun
from app.models.feedback import MessageFeedback
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.models.message import Citation, Message
from app.models.ticket import Ticket, TicketNote
from app.models.user import User
from app.schemas.admin import DemoResetResponse
from app.seed import seed_demo_knowledge_into
from app.services.audit import record_event
from app.services.eval_seed import ensure_eval_metadata


async def _count(db: AsyncSession, model: type) -> int:
    result = await db.execute(select(func.count()).select_from(model))
    return int(result.scalar_one())


async def reset_demo_data(
    db: AsyncSession, *, user: User, request_id: str
) -> DemoResetResponse:
    if not settings.demo_mode:
        raise AppError("NOT_FOUND", "演示模式未启用", 404)
    models = [
        ("message_feedback", MessageFeedback),
        ("citations", Citation),
        ("messages", Message),
        ("ticket_notes", TicketNote),
        ("tickets", Ticket),
        ("workflow_checkpoints", WorkflowCheckpoint),
        ("tool_executions", ToolExecution),
        ("approvals", Approval),
        ("actions", ActionRequest),
        ("cases", Case),
        ("knowledge_chunks", KnowledgeChunk),
        ("knowledge_documents", KnowledgeDocument),
        ("eval_results", EvalResult),
        ("eval_runs", EvalRun),
        ("eval_items", EvalItem),
        ("eval_datasets", EvalDataset),
        ("prompt_versions", PromptVersion),
        ("tool_policies", ToolPolicy),
        ("system_settings", SystemSetting),
    ]
    deleted = {name: await _count(db, model) for name, model in models}
    for _name, model in models:
        await db.execute(delete(model))
    await db.flush()

    documents = await seed_demo_knowledge_into(db, user.id)
    await ensure_eval_metadata(db, owner_id=user.id)
    event = await record_event(
        db,
        event_type="demo.reset",
        actor_id=user.id,
        actor_role=user.role,
        request_id=request_id,
        payload={
            "deleted": deleted,
            "reseeded_documents": documents,
            "tool_policies": "reset_to_defaults",
            "kill_switch": False,
        },
    )
    await db.flush()
    await db.commit()
    return DemoResetResponse(
        reset_at=utcnow(),
        deleted=deleted,
        reseeded_documents=documents,
        audit_event_id=event.id,
        message="演示数据已重置到初始基线；审计历史保留，工具状态恢复为默认启用/成功模式。",
    )
