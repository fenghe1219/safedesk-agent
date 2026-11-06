from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import as_utc, utcnow
from app.models.action import ActionRequest, Approval, ToolExecution
from app.models.audit import AuditEvent
from app.models.case import Case
from app.models.eval import EvalDataset, EvalRun
from app.models.ticket import Ticket
from app.schemas.dashboard import DashboardResponse, DistributionItem, EvalTrendPoint
from app.services.evaluation import KEY_METRICS, METRIC_LABELS
from app.services.triage import CATEGORY_LABELS, PRIORITY_LABELS


def _rate(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else 0.0


def _distribution(
    rows: list[Any], attribute: str, labels: dict[str, str]
) -> list[DistributionItem]:
    counts = Counter(str(getattr(row, attribute)) for row in rows if getattr(row, attribute))
    total = sum(counts.values())
    return [
        DistributionItem(
            key=key,
            label=labels.get(key, key),
            count=count,
            rate=_rate(count, total),
        )
        for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _average(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


async def build_dashboard(db: AsyncSession, *, range_key: str) -> DashboardResponse:
    days = 30 if range_key == "30d" else 7
    start = utcnow() - timedelta(days=days)
    cases = list(
        (
            await db.execute(select(Case).where(Case.created_at >= start))
        ).scalars().all()
    )
    tickets = list(
        (
            await db.execute(select(Ticket).where(Ticket.created_at >= start))
        ).scalars().all()
    )
    approvals = list(
        (
            await db.execute(select(Approval).where(Approval.requested_at >= start))
        ).scalars().all()
    )
    failed_actions = list(
        (
            await db.execute(
                select(ActionRequest).where(
                    ActionRequest.status == "FAILED", ActionRequest.updated_at >= start
                )
            )
        ).scalars().all()
    )
    executions = list(
        (
            await db.execute(select(ToolExecution).where(ToolExecution.started_at >= start))
        ).scalars().all()
    )
    events = list(
        (
            await db.execute(
                select(AuditEvent)
                .where(AuditEvent.created_at >= start)
                .order_by(AuditEvent.created_at.desc())
                .limit(10000)
            )
        ).scalars().all()
    )
    eval_runs = (
        await db.execute(
            select(EvalRun, EvalDataset.dataset_type)
            .join(EvalDataset, EvalRun.dataset_id == EvalDataset.id)
            .where(EvalRun.status == "COMPLETED", EvalRun.created_at >= start)
            .order_by(EvalRun.created_at.desc())
            .limit(8)
        )
    ).all()

    cases_total = len(cases)
    knowledge_cases = sum(
        1
        for case in cases
        if case.status in {"ANSWERED", "RESOLVED"}
        and case.ticket_id is None
        and case.action_id is None
    )
    ticket_cases = sum(1 for case in cases if case.ticket_id is not None)
    approval_requests = len(approvals)
    approval_rejected = sum(1 for approval in approvals if approval.status == "REJECTED")
    approval_approved = sum(1 for approval in approvals if approval.status == "APPROVED")
    approval_expired = sum(1 for approval in approvals if approval.status == "EXPIRED")
    decided = [
        approval
        for approval in approvals
        if approval.status in {"APPROVED", "REJECTED"} and approval.decided_at is not None
    ]
    wait_minutes = [
        max(0.0, (as_utc(item.decided_at) - as_utc(item.requested_at)).total_seconds() / 60)
        for item in decided
        if item.decided_at is not None
    ]
    handling_minutes = [
        max(0.0, (as_utc(item.updated_at) - as_utc(item.created_at)).total_seconds() / 60)
        for item in cases
        if item.status in {"RESOLVED", "CANCELLED"}
    ]
    corrected_ticket_ids = {
        str(event.payload.get('ticket_id'))
        for event in events
        if event.event_type == 'ticket.updated'
        and event.payload.get('ticket_id')
        and event.payload.get('changed_fields')
    }
    duplicate_blocked = sum(
        1 for event in events if event.event_type == "tool.duplicate_blocked"
    )
    answer_latencies = [
        float(event.payload.get("latency_ms"))
        for event in events
        if event.event_type in {"answer.generated", "answer.refused"}
        and isinstance(event.payload.get("latency_ms"), (int, float))
    ]
    retrieval_latencies = [
        float(event.payload.get("latency_ms"))
        for event in events
        if event.event_type == "retrieval.completed"
        and isinstance(event.payload.get("latency_ms"), (int, float))
    ]
    answer_costs = [
        float(event.payload.get("cost_usd"))
        for event in events
        if event.event_type in {"answer.generated", "answer.refused"}
        and isinstance(event.payload.get("cost_usd"), (int, float))
    ]
    tool_latencies = [
        max(0.0, (as_utc(item.finished_at) - as_utc(item.started_at)).total_seconds() * 1000)
        for item in executions
        if item.finished_at is not None
    ]

    trend: list[EvalTrendPoint] = []
    for run, dataset_type in eval_runs:
        metric_key = next(
            (key for key in KEY_METRICS.get(dataset_type, ()) if key in (run.metrics or {})),
            "pass_rate",
        )
        if not metric_key or metric_key not in (run.metrics or {}):
            continue
        trend.append(
            EvalTrendPoint(
                run_id=run.id,
                dataset_type=dataset_type,
                label=run.label,
                sample_size=run.sample_count,
                pass_rate=float((run.metrics or {}).get("pass_rate", 0.0)),
                key_metric=metric_key,
                key_metric_label=METRIC_LABELS.get(metric_key, "通过率"),
                key_metric_value=float((run.metrics or {}).get(metric_key, 0.0)),
                created_at=run.created_at,
            )
        )

    return DashboardResponse(
        range=range_key,
        range_label=f"最近 {days} 天",
        generated_at=utcnow(),
        cases_total=cases_total,
        knowledge_resolution_rate=_rate(knowledge_cases, cases_total),
        ticket_rate=_rate(ticket_cases, cases_total),
        approval_requests=approval_requests,
        approval_rejected=approval_rejected,
        approval_failed=len(failed_actions),
        category_distribution=_distribution(tickets, "category", CATEGORY_LABELS),
        priority_distribution=_distribution(tickets, "priority", PRIORITY_LABELS),
        manual_correction_rate=_rate(len(corrected_ticket_ids), len(tickets)),
        avg_handling_minutes=_average(handling_minutes),
        approval_pass_rate=_rate(approval_approved, len(decided)),
        avg_approval_wait_minutes=_average(wait_minutes),
        approval_expiry_rate=_rate(approval_expired, approval_requests),
        duplicate_execution_blocked=duplicate_blocked,
        avg_answer_latency_ms=_average(answer_latencies),
        avg_retrieval_latency_ms=_average(retrieval_latencies),
        avg_tool_latency_ms=_average(tool_latencies),
        avg_answer_cost_usd=round(_average(answer_costs), 8),
        eval_trend=trend,
        sample_sizes={
            "cases_total": cases_total,
            "knowledge_resolution_rate": cases_total,
            "ticket_rate": cases_total,
            "approval_requests": approval_requests,
            "approval_pass_rate": len(decided),
            "approval_expiry_rate": approval_requests,
            "manual_correction_rate": len(tickets),
            "avg_handling_minutes": len(handling_minutes),
            "avg_answer_latency_ms": len(answer_latencies),
            "avg_retrieval_latency_ms": len(retrieval_latencies),
            "avg_tool_latency_ms": len(tool_latencies),
            "avg_answer_cost_usd": len(answer_costs),
            "eval_trend": len(trend),
        },
        methodology={
            "knowledge_resolution": (
                "知识解决率 = 已回答/已解决且没有转工单或写动作的 "
                "Case / Case 总量"
            ),
            "ticket_rate": "转单率 = 已关联工单的 Case / Case 总量",
            "manual_correction": (
                "人工修正率 = 发生字段修改的不同工单数 / 工单总量；"
                "备注和状态流转不计入"
            ),
            "approval_pass": "审批通过率 = 已批准 /（已批准 + 已拒绝）",
            "latency": "回答与检索延迟来自审计事件；工具延迟来自 ToolExecution 起止时间",
            "cost": "本地规则基线使用可解释的估算成本，不代表外部模型账单",
        },
    )
