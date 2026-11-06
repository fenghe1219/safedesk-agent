from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import ROLE_LABELS, Role
from app.models.ticket import Ticket
from app.models.user import User

CATEGORY_LABELS: dict[str, str] = {
    "account_permission": "账号与权限",
    "network_vpn": "网络与 VPN",
    "software": "软件与安装",
    "hardware": "硬件与设备",
    "email_collaboration": "邮箱与协作工具",
    "security_incident": "安全事件",
    "other": "其他",
}

PRIORITY_LABELS: dict[str, str] = {
    "P1": "P1 紧急",
    "P2": "P2 高",
    "P3": "P3 常规",
    "P4": "P4 低",
}

FIELD_LABELS: dict[str, str] = {
    "title": "问题标题",
    "description": "问题描述",
    "category": "分类",
    "priority": "优先级",
    "priority_reason": "优先级理由",
    "affected_system": "影响系统",
    "environment": "操作系统或设备环境",
    "error_message": "具体报错或错误码",
    "urgency_reason": "紧急原因",
}

ACTIVE_TICKET_STATUSES = ("OPEN", "ASSIGNED", "IN_PROGRESS", "REOPENED")

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "security_incident": (
        "病毒",
        "木马",
        "钓鱼",
        "勒索",
        "入侵",
        "数据泄露",
        "异常登录",
        "异地登录",
        "可疑",
        "可疑进程",
        "安全事件",
        "文件被加密",
        "账号被盗",
        "被盗",
        "冒充",
        "杀毒",
        "报警",
        "泄露",
    ),
    "network_vpn": (
        "vpn",
        "网络",
        "断网",
        "连不上",
        "无法连接",
        "证书",
        "wifi",
        "无线",
        "dns",
        "网关",
        "代理",
        "内网",
    ),
    "hardware": (
        "打印机",
        "打印",
        "电脑",
        "笔记本",
        "显示器",
        "键盘",
        "鼠标",
        "硬盘",
        "蓝屏",
        "驱动",
        "投影",
        "扫描仪",
        "设备",
        "耗材",
        "无法开机",
    ),
    "email_collaboration": (
        "邮箱",
        "邮件",
        "outlook",
        "会议",
        "日历",
        "teams",
        "企业微信",
        "飞书",
        "协作",
        "共享",
    ),
    "software": (
        "软件",
        "安装",
        "卸载",
        "客户端",
        "应用",
        "更新",
        "崩溃",
        "许可",
        "license",
        "激活",
        "版本",
    ),
    "account_permission": (
        "账号",
        "账户",
        "密码",
        "登录",
        "锁定",
        "权限",
        "域账号",
        "sso",
        "mfa",
        "解锁",
        "停用",
        "无法登录",
        "重置",
    ),
}

CATEGORY_DEPARTMENTS: dict[str, tuple[str, ...]] = {
    "account_permission": ("IT 管理", "桌面支持"),
    "network_vpn": ("桌面支持", "IT 管理"),
    "software": ("桌面支持", "IT 管理"),
    "hardware": ("桌面支持", "IT 管理"),
    "email_collaboration": ("桌面支持", "IT 管理"),
    "security_incident": ("IT 管理", "桌面支持"),
    "other": ("桌面支持", "IT 管理"),
}

CATEGORY_SYSTEMS: dict[str, str] = {
    "account_permission": "公司账号",
    "network_vpn": "企业网络",
    "software": "办公软件",
    "hardware": "办公终端",
    "email_collaboration": "邮箱与协作工具",
    "security_incident": "终端安全",
    "other": "IT 服务",
}

_TICKET_PATTERNS = (
    re.compile(r"(创建|新建|建|开|提|提交|发起|转|升级).{0,3}(工单|报修|服务单)"),
    re.compile(r"(工单|报修).{0,3}(创建|提交|处理)"),
    re.compile(r"(转|找|联系).{0,2}(人工|支持|it)"),
    re.compile(r"(建单|提单|开工单|报工单)"),
    re.compile(r"报修"),
)

_ISSUE_PATTERN = re.compile(
    r"无法|不能|失败|报错|错误|异常|坏了|故障|中断|崩溃|打不开|连不上|登录不了|锁定|"
    r"蓝屏|卡死|丢失|泄露|中毒"
)

_ISSUE_HINTS = (
    "打印机",
    "打印",
    "电脑",
    "笔记本",
    "显示器",
    "键盘",
    "鼠标",
    "蓝屏",
    "驱动",
    "vpn",
    "网络",
    "断网",
    "wifi",
    "软件",
    "安装",
    "卸载",
    "客户端",
    "账号",
    "账户",
    "密码",
    "登录",
    "锁定",
    "权限",
    "邮箱",
    "邮件",
    "outlook",
    "会议",
    "日历",
    "teams",
    "病毒",
    "钓鱼",
    "勒索",
    "安全",
    "报错",
    "错误码",
    "服务器",
)

_P1_TERMS = (
    "多人",
    "全员",
    "全公司",
    "整个部门",
    "大面积",
    "核心业务",
    "生产环境",
    "宕机",
    "数据泄露",
    "勒索",
    "入侵",
    "病毒",
    "钓鱼",
    "无法营业",
    "重大损失",
    "多台",
)
_P2_TERMS = (
    "无法工作",
    "不能工作",
    "完全无法",
    "无法使用",
    "无法访问",
    "无法登录",
    "无法重装",
    "不能用",
    "连不上",
    "掉线",
    "打不开",
    "崩溃",
    "蓝屏",
    "鼓包",
    "wifi",
    "影响交付",
    "客户来访",
    "客户邮件",
    "客户投诉",
    "上线",
    "截止",
    "今天",
    "明天",
    "下周",
    "本周",
    "会议",
    "紧急",
    "马上",
    "尽快",
    "关键岗位",
    "坏了",
    "故障",
    "报错",
    "失败",
)
_P3_WORKAROUND_TERMS = (
    "临时",
    "替代",
    "其他电脑",
    "另一台",
    "手机热点",
    "网页版",
    "可以先用",
    "不影响",
)
_P4_TERMS = (
    "咨询",
    "建议",
    "优化",
    "了解",
    "如何",
    "怎么申请",
    "是否",
    "能否",
    "想确认",
    "几点",
    "搬迁申请",
    "流程",
    "申领",
    "查询",
)

_ERROR_CODE_RE = re.compile(r"0x[0-9a-fA-F]{4,}|[A-Za-z]{2,}[-_]\d{2,}")
_ERROR_CONTEXT_RE = re.compile(r"(?:报错|错误码|错误|提示|失败|异常)[^。\n；;]{0,120}")

_ENVIRONMENT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"Windows\s*(?:11|10|8\.1|7|Server\s*\d{4})", re.IGNORECASE), ""),
    (re.compile(r"macOS(?:\s*\d+(?:\.\d+)?)?", re.IGNORECASE), ""),
    (re.compile(r"Linux", re.IGNORECASE), ""),
    (re.compile(r"iOS", re.IGNORECASE), ""),
    (re.compile(r"Android", re.IGNORECASE), ""),
    (re.compile(r"iPad", re.IGNORECASE), ""),
    (re.compile(r"公司电脑|办公电脑|家里|远程办公|办公室|手机|平板|浏览器"), ""),
)

_STRONG_CATEGORY_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("network_vpn", ("vpn", "断网", "无法上网", "wifi", "无线网络", "内网")),
    ("hardware", ("打印机", "蓝屏", "显示器", "键盘", "鼠标", "投影仪")),
    ("email_collaboration", ("outlook", "邮箱", "邮件", "企业微信")),
    ("software", ("软件", "客户端", "安装软件")),
    ("account_permission", ("账号", "账户", "密码")),
)


@dataclass(frozen=True)
class AssigneeRecommendation:
    user: User | None
    reason: str
    open_ticket_count: int = 0


@dataclass(frozen=True)
class TriageDraft:
    title: str
    description: str
    category: str
    category_label: str
    category_confidence: float
    priority: str
    priority_label: str
    priority_reason: str
    affected_system: str | None
    environment: str | None
    error_message: str | None
    urgency_reason: str | None
    missing_fields: list[str]

    def to_fields(self) -> dict[str, object]:
        return {
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "priority": self.priority,
            "priority_reason": self.priority_reason,
            "affected_system": self.affected_system,
            "environment": self.environment,
            "error_message": self.error_message,
            "urgency_reason": self.urgency_reason,
            "category_confidence": self.category_confidence,
        }


def asks_for_ticket(text: str) -> bool:
    lowered = text.lower()
    return any(pattern.search(lowered) for pattern in _TICKET_PATTERNS)


def looks_like_it_issue(text: str) -> bool:
    lowered = text.lower()
    return any(hint in lowered for hint in _ISSUE_HINTS)


def build_triage(messages: Iterable[str]) -> TriageDraft:
    texts = [message.strip() for message in messages if message and message.strip()]
    text = "\n".join(texts)[-6000:]
    category, confidence = classify_category(text)
    priority, priority_reason, urgency_reason = choose_priority(text, category)
    environment = extract_environment(text)
    error_message = extract_error_message(text)
    affected_system = infer_affected_system(text, category)
    title = infer_title(texts, category)
    description = text[:2000]
    missing_fields = find_missing_fields(
        text=text,
        description=description,
        category=category,
        environment=environment,
        error_message=error_message,
    )
    return TriageDraft(
        title=title,
        description=description,
        category=category,
        category_label=CATEGORY_LABELS[category],
        category_confidence=confidence,
        priority=priority,
        priority_label=PRIORITY_LABELS[priority],
        priority_reason=priority_reason,
        affected_system=affected_system,
        environment=environment,
        error_message=error_message,
        urgency_reason=urgency_reason,
        missing_fields=missing_fields,
    )


def classify_category(text: str) -> tuple[str, float]:
    lowered = text.lower()
    if any(keyword.lower() in lowered for keyword in CATEGORY_KEYWORDS["security_incident"]):
        return "security_incident", 0.95
    for category, hints in _STRONG_CATEGORY_HINTS:
        if any(hint in lowered for hint in hints):
            return category, 0.9
    scores: dict[str, float] = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = 0.0
        for keyword in keywords:
            target = keyword.lower()
            if target in lowered:
                score += 1.0 + min(len(target), 8) * 0.08
        if score:
            scores[category] = score
    if not scores:
        return "other", 0.3
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    category, top_score = ordered[0]
    total = sum(scores.values())
    confidence = min(0.99, max(0.35, top_score / total))
    return category, round(confidence, 2)


def choose_priority(text: str, category: str) -> tuple[str, str, str | None]:
    lowered = text.lower()
    if category == "security_incident" or any(term in lowered for term in _P1_TERMS):
        return (
            "P1",
            "存在多人影响、核心业务中断或安全事件特征，需立即升级处理。",
            extract_urgency_reason(text) or "疑似安全事件或大面积影响，需立即响应。",
        )
    if any(term in lowered for term in _P4_TERMS):
        return (
            "P4",
            "属于咨询、建议或非紧急问题，不影响当前工作。",
            None,
        )
    if any(term in lowered for term in _P2_TERMS):
        return (
            "P2",
            "单人工作受阻或存在明确时限，需要尽快处理。",
            extract_urgency_reason(text),
        )
    if any(term in lowered for term in _P3_WORKAROUND_TERMS):
        return (
            "P3",
            "存在临时替代方案，影响有限，可按常规队列处理。",
            None,
        )
    return (
        "P3",
        "问题影响有限，按常规队列处理。",
        None,
    )


def extract_urgency_reason(text: str) -> str | None:
    match = re.search(
        r"(今天|明天|本周|下周|会议|上线|截止|尽快|马上|紧急|客户|交付)[^。\n；;]{0,60}",
        text,
    )
    if match is None:
        return None
    return match.group(0).strip()[:300]


def extract_environment(text: str) -> str | None:
    values: list[str] = []
    for pattern, _ in _ENVIRONMENT_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(0).strip()
            if value and value not in values:
                values.append(value)
    if not values:
        return None
    return " / ".join(values[:3])[:120]


def extract_error_message(text: str) -> str | None:
    codes = _ERROR_CODE_RE.findall(text)
    contexts = [item.strip() for item in _ERROR_CONTEXT_RE.findall(text)]
    parts: list[str] = []
    for code in codes:
        if code not in parts:
            parts.append(code)
    for context in contexts:
        if context and context not in parts:
            parts.append(context)
    if not parts:
        return None
    return "；".join(parts)[:1000]


def infer_affected_system(text: str, category: str) -> str:
    lowered = text.lower()
    if "vpn" in lowered:
        return "企业 VPN"
    if "打印" in text:
        return "网络打印机"
    if any(term in lowered for term in ("outlook", "邮箱", "邮件")):
        return "企业邮箱"
    if any(term in lowered for term in ("teams", "会议", "日历", "企业微信", "飞书")):
        return "协作工具"
    if any(term in text for term in ("账号", "账户", "密码", "登录", "锁定", "权限")):
        return "公司账号"
    if any(term in text for term in ("电脑", "笔记本", "显示器", "键盘", "鼠标", "蓝屏")):
        return "办公终端"
    if any(term in text for term in ("病毒", "钓鱼", "勒索", "安全")):
        return "终端安全"
    if any(term in text for term in ("软件", "安装", "客户端", "应用")):
        return "办公软件"
    return CATEGORY_SYSTEMS.get(category, "IT 服务")


def infer_title(texts: list[str], category: str) -> str:
    first = texts[0].splitlines()[0] if texts else ""
    cleaned = re.sub(
        r"(请|麻烦|帮我|我想|需要|能不能|可以)?\s*"
        r"(创建|新建|建|开|提|提交|发起|转|升级)\s*(一个|个)?\s*(工单|报修单|服务单)",
        "",
        first,
    )
    cleaned = cleaned.strip(" ，,。.；;")
    if not cleaned:
        cleaned = f"{CATEGORY_LABELS[category]}问题"
    if len(cleaned) > 60:
        cleaned = f"{cleaned[:60].rstrip()}…"
    return cleaned[:120]


def find_missing_fields(
    *,
    text: str,
    description: str,
    category: str,
    environment: str | None,
    error_message: str | None,
) -> list[str]:
    missing: list[str] = []
    issue_like = bool(_ISSUE_PATTERN.search(text))
    if len(description.strip()) < 8:
        missing.append("description")
    if category == "security_incident":
        return missing
    needs_environment = category in {
        "hardware",
        "software",
        "network_vpn",
        "email_collaboration",
    }
    if issue_like and needs_environment and environment is None:
        missing.append("environment")
    needs_error = category in {"hardware", "software", "network_vpn"}
    if issue_like and needs_error and error_message is None:
        missing.append("error_message")
    return missing


def build_followup_prompt(draft: TriageDraft) -> str:
    labels = [FIELD_LABELS.get(field, field) for field in draft.missing_fields[:3]]
    if not labels:
        return "可以帮你转成工单。请确认下面的分类、优先级和字段，确认前不会创建工单。"
    items = "\n".join(f"{index}. {label}" for index, label in enumerate(labels, start=1))
    return (
        "可以帮你转成工单，但还缺少关键信息。\n\n"
        "为了准确分诊，请补充：\n"
        f"{items}\n\n"
        "补充后我会生成工单草稿；确认前不会创建工单。"
    )


async def recommend_assignee(
    db: AsyncSession, category: str
) -> AssigneeRecommendation:
    roles = (Role.SUPPORT.value, Role.ADMIN.value)
    result = await db.execute(
        select(User).where(User.is_active.is_(True), User.role.in_(roles))
    )
    candidates = list(result.scalars().all())
    if not candidates:
        return AssigneeRecommendation(user=None, reason="当前没有可用的支持人员。")

    counts_result = await db.execute(
        select(Ticket.assignee_id, func.count(Ticket.id))
        .where(
            Ticket.status.in_(ACTIVE_TICKET_STATUSES),
            Ticket.assignee_id.is_not(None),
        )
        .group_by(Ticket.assignee_id)
    )
    counts = {assignee_id: count for assignee_id, count in counts_result.all()}
    preferred_departments = CATEGORY_DEPARTMENTS.get(category, CATEGORY_DEPARTMENTS["other"])

    def sort_key(user: User) -> tuple[int, int, str]:
        if user.department in preferred_departments:
            department_rank = preferred_departments.index(user.department)
        else:
            department_rank = len(preferred_departments)
        return (department_rank, counts.get(user.id, 0), user.name)

    chosen = min(candidates, key=sort_key)
    open_count = counts.get(chosen.id, 0)
    if chosen.department in preferred_departments:
        reason = (
            f"属于「{chosen.department}」技能组，匹配{CATEGORY_LABELS[category]}；"
            f"当前活跃工单 {open_count} 个，负载最低。"
        )
    else:
        reason = (
            f"当前没有完全匹配技能组的空闲人员，暂选 {chosen.name}；"
            f"当前活跃工单 {open_count} 个。"
        )
    return AssigneeRecommendation(user=chosen, reason=reason, open_ticket_count=open_count)


def assignee_role_label(user: User) -> str:
    return ROLE_LABELS.get(user.role, user.role)
