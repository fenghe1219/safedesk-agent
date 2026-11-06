from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.rbac import has_permission
from app.models.audit import AuditEvent
from app.models.case import Case
from app.models.user import User
from app.schemas.case import CaseOut, TimelineEventOut

CASE_STATUS_LABELS: dict[str, str] = {
    "NEW": "新问题",
    "UNDERSTANDING": "正在理解",
    "RETRIEVING": "正在检索",
    "DIAGNOSING": "正在核对依据",
    "NEEDS_INPUT": "等待补充",
    "ANSWERED": "已回答",
    "TICKET_DRAFT": "工单待确认",
    "TICKET_OPEN": "已转工单",
    "ACTION_PROPOSED": "动作待确认",
    "AWAITING_APPROVAL": "等待审批",
    "EXECUTING": "执行中",
    "REJECTED": "审批未通过",
    "EXPIRED": "审批已过期",
    "RESOLVED": "已解决",
    "FAILED": "执行失败",
    "CANCELLED": "已关闭",
    "REFUSED": "无法处理",
}

CASE_PHASES: dict[str, str] = {
    "NEW": "intake",
    "UNDERSTANDING": "intake",
    "RETRIEVING": "retrieval",
    "DIAGNOSING": "retrieval",
    "NEEDS_INPUT": "retrieval",
    "ANSWERED": "solution",
    "TICKET_DRAFT": "solution",
    "TICKET_OPEN": "solution",
    "REFUSED": "solution",
    "ACTION_PROPOSED": "approval",
    "AWAITING_APPROVAL": "approval",
    "EXECUTING": "approval",
    "REJECTED": "approval",
    "EXPIRED": "approval",
    "FAILED": "approval",
    "RESOLVED": "done",
    "CANCELLED": "done",
}

EVENT_SUMMARIES: dict[str, str] = {
    "case.created": "创建 Case",
    "case.updated": "更新 Case",
    "case.closed": "关闭 Case",
    "case.reopened": "重新打开 Case",
    "message.received": "收到用户消息",
    "answer.generated": "生成回答",
    "answer.refused": "拒答",
    "retrieval.completed": "完成知识检索",
    "evidence.insufficient": "证据不足",
    "ticket.created": "创建工单",
    "ticket.drafted": "生成工单草稿",
    "ticket.updated": "更新工单",
    "ticket.transitioned": "流转工单状态",
    "action.proposed": "提议动作",
    "action.cancelled": "取消动作",
    "approval.requested": "请求审批",
    "approval.approved": "审批通过",
    "approval.rejected": "审批拒绝",
    "approval.expired": "审批过期",
    "tool.executed": "执行工具",
    "tool.executing": "开始执行工具",
    "tool.failed": "工具执行失败",
    "tool.duplicate_blocked": "重复执行已拦截",
    "tool.read_executed": "执行只读诊断工具",
    "tool.read_failed": "只读诊断工具失败",
    "action.verified": "验证执行结果",
    "action.verification_failed": "执行结果验证失败",
    "case.resolved": "Case 已解决",
    "config.changed": "更新系统配置",
    "auth.login": "登录",
    "auth.logout": "退出",
    "auth.demo_switch": "切换演示身份",
    "knowledge.document_imported": "导入知识文档",
    "knowledge.document_reindexed": "重建知识索引",
    "knowledge.document_updated": "更新知识文档",
    "knowledge.document_deleted": "删除知识文档",
    "eval.run_completed": "完成评估运行",
    "eval.result_reviewed": "人工复核评估样本",
    "eval.dataset_imported": "导入评估数据集",
    "demo.reset": "重置演示数据",
    "feedback.submitted": "提交回答反馈",
}


async def get_accessible_case(db: AsyncSession, user: User, case_id: str) -> Case:
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if case is None:
        raise AppError("NOT_FOUND", "Case 不存在", 404)
    if case.requester_id != user.id and not has_permission(user.role, "case:read_all"):
        raise AppError("NOT_FOUND", "Case 不存在", 404)
    return case


def to_case_out(case: Case) -> CaseOut:
    return CaseOut(
        id=case.id,
        title=case.title,
        status=case.status,
        status_label=CASE_STATUS_LABELS.get(case.status, case.status),
        phase=CASE_PHASES.get(case.status, "intake"),
        requester_id=case.requester_id,
        current_node=case.current_node,
        intent=case.intent,
        ticket_id=case.ticket_id,
        action_id=case.action_id,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def to_timeline_event(event: AuditEvent) -> TimelineEventOut:
    return TimelineEventOut(
        id=event.id,
        event_type=event.event_type,
        summary=EVENT_SUMMARIES.get(event.event_type, event.event_type),
        actor_id=event.actor_id,
        actor_role=event.actor_role,
        result=event.result,
        created_at=event.created_at,
    )
