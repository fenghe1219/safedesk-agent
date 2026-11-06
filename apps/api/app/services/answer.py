from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.knowledge import KnowledgeChunk, KnowledgeDocument
from app.services.retrieval import RetrievalHit, select_quote

MODEL_VERSION = "extractive-rag-v1"
PROMPT_VERSION = "m1-knowledge-v1"


@dataclass(frozen=True)
class CitationPlan:
    document: KnowledgeDocument
    chunk: KnowledgeChunk
    quote: str
    index: int


@dataclass(frozen=True)
class AnswerPlan:
    content: str
    citations: list[CitationPlan]
    refused: bool
    intent: str
    evidence_count: int


_REFUSAL_PATTERNS = [
    re.compile(r"(同事|他人|别人).{0,12}(薪资|工资|薪酬|绩效|住址|身份证|手机号)"),
    re.compile(r"(查看|查询|获取|导出).{0,10}(同事|他人|别人).{0,10}(信息|工资|薪资|薪酬)"),
    re.compile(r"(忽略|绕过|无视|覆盖).{0,10}(指令|规则|策略|系统提示|安全策略)"),
    re.compile(r"(执行|运行).{0,8}(shell|命令|脚本|rm\s+-rf|powershell)"),
    re.compile(r"(系统提示词|system\s*prompt|开发者指令|隐藏规则)"),
    re.compile(r"(明文|批量).{0,8}(密码|凭据|密钥).{0,8}(导出|查看|列表)"),
]

_STEP_HINTS = (
    "打开",
    "关闭",
    "点击",
    "选择",
    "进入",
    "检查",
    "确认",
    "重置",
    "重新",
    "连接",
    "安装",
    "更新",
    "重启",
    "联系",
    "提交",
    "登录",
    "解锁",
    "等待",
    "使用",
)


def build_answer(
    query: str,
    hits: list[RetrievalHit],
    *,
    max_citations: int = 4,
    style: str = 'concise',
) -> AnswerPlan:
    intent = detect_intent(query)
    refusal = sensitive_refusal(query)
    if refusal is not None:
        return AnswerPlan(
            content=refusal,
            citations=[],
            refused=True,
            intent=intent,
            evidence_count=0,
        )

    if not hits:
        return AnswerPlan(
            content=(
                "知识库中暂未找到足以回答这个问题的依据。\n\n"
                "你可以：\n"
                "1. 补充具体报错、设备型号、操作系统或发生时间。\n"
                "2. 创建工单转人工核实，避免依据不足时猜测操作步骤。"
            ),
            citations=[],
            refused=True,
            intent=intent,
            evidence_count=0,
        )

    citations: list[CitationPlan] = []
    used_chunks: set[str] = set()
    for hit in hits:
        if hit.chunk.id in used_chunks:
            continue
        used_chunks.add(hit.chunk.id)
        citations.append(
            CitationPlan(
                document=hit.document,
                chunk=hit.chunk,
                quote=select_quote(hit.chunk.content, query),
                index=len(citations) + 1,
            )
        )
        if len(citations) >= max(1, max_citations):
            break

    primary = citations[0]
    conclusion = primary.quote.rstrip("。")
    if len(conclusion) > 180:
        conclusion = conclusion[:180].rstrip() + "…"
    conclusion = f"根据《{primary.document.title}》，{conclusion}。[1]"

    steps: list[tuple[str, int]] = []
    for citation in citations:
        for step in _extract_steps(citation.chunk.content):
            normalized = step.rstrip("。；;")
            if all(normalized != existing for existing, _ in steps):
                steps.append((normalized, citation.index))
            if len(steps) >= (4 if style == 'concise' else 6):
                break
        if len(steps) >= (4 if style == 'concise' else 6):
            break
    if not steps:
        steps.append((f"按《{primary.document.title}》中的说明逐项排查", 1))

    step_text = "\n".join(
        f"{index}. {step}。[{citation_index}]"
        for index, (step, citation_index) in enumerate(steps, start=1)
    )
    evidence_summary = ''
    if style == 'detailed':
        evidence_summary = '\n\n依据摘要\n' + '\n'.join(
            f'- {citation.quote} [{citation.index}]' for citation in citations[:3]
        )
    content = (
        "结论\n"
        f"{conclusion}\n\n"
        "处理步骤\n"
        f"{step_text}"
        f"{evidence_summary}\n\n"
        "下一步\n"
        "完成上述步骤后重新验证。如果问题仍然存在，请补充仍出现的报错、设备或时间信息，"
        "我会继续核对知识依据；也可以创建工单转人工处理。"
    )
    return AnswerPlan(
        content=content,
        citations=citations,
        refused=False,
        intent=intent,
        evidence_count=len(citations),
    )


def detect_intent(query: str) -> str:
    lowered = query.lower()
    if "vpn" in lowered or "证书" in query:
        return "vpn_connectivity"
    if "打印" in query or "0x0000011b" in lowered:
        return "printer"
    if any(term in query for term in ("账号", "账户", "密码", "锁定", "登录")):
        return "account_access"
    if any(term in query for term in ("工资", "薪资", "薪酬", "隐私", "权限")):
        return "sensitive_access"
    return "knowledge_question"


def sensitive_refusal(query: str) -> str | None:
    if any(pattern.search(query) for pattern in _REFUSAL_PATTERNS):
        return (
            "这类请求涉及他人隐私、账号安全或系统权限，我无法直接处理。\n\n"
            "你可以：\n"
            "1. 查询本人的账号与权限说明。\n"
            "2. 创建工单，由有权限的人工人员核实后处理。"
        )
    return None


def _extract_steps(content: str) -> list[str]:
    candidates: list[str] = []
    for raw_line in content.splitlines():
        line = re.sub(r"^\s*(?:[-*•]|\d+[.)、])\s*", "", raw_line).strip()
        if not line or line.startswith("#") or len(line) < 6:
            continue
        if any(hint in line for hint in _STEP_HINTS):
            candidates.append(line)

    if not candidates:
        for sentence in re.split(r"(?<=[。！？!?])", content):
            line = sentence.strip()
            if len(line) >= 8 and any(hint in line for hint in _STEP_HINTS):
                candidates.append(line)
    return candidates[:4]
