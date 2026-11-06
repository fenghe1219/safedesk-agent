import json
import re
from datetime import datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import new_id, utcnow
from app.models.action import ActionRequest, Approval, ToolExecution
from app.models.audit import AuditEvent
from app.models.case import Case
from app.models.eval import EvalDataset, EvalRun
from app.models.feedback import MessageFeedback
from app.models.knowledge import KnowledgeDocument
from app.models.ticket import Ticket
from app.services.eval_seed import ensure_eval_metadata
from tests.conftest import TestSession, csrf_headers, login


async def switch_user(client: AsyncClient, email: str) -> None:
    await client.post("/api/auth/logout", headers=csrf_headers(client))
    response = await login(client, email)
    assert response.status_code == 200, response.text


def sse_events(body: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for frame in body.split("\n\n"):
        event = re.search(r"^event: (.+)$", frame, re.MULTILINE)
        data = re.search(r"^data: (.+)$", frame, re.MULTILINE)
        if event and data:
            events.append((event.group(1), json.loads(data.group(1))))
    return events


async def create_case(client: AsyncClient, title: str) -> dict[str, Any]:
    response = await client.post(
        "/api/cases", json={"title": title}, headers=csrf_headers(client)
    )
    assert response.status_code == 201, response.text
    return response.json()


async def send_message(
    client: AsyncClient, case_id: str, content: str
) -> list[tuple[str, dict[str, Any]]]:
    response = await client.post(
        f"/api/cases/{case_id}/messages",
        json={"content": content},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200, response.text
    return sse_events(response.text)


async def seed_dashboard_data() -> dict[str, str]:
    now = utcnow()
    ids = {
        "knowledge_case": new_id("case"),
        "ticket_case": new_id("case"),
        "approval_case": new_id("case"),
        "failed_case": new_id("case"),
        "old_case": new_id("case"),
        "ticket": new_id("ticket"),
        "approved_action": new_id("act"),
        "rejected_action": new_id("act"),
        "failed_action": new_id("act"),
        "execution": new_id("exec"),
    }
    async with TestSession() as db:
        db.add_all(
            [
                Case(
                    id=ids["knowledge_case"],
                    title="VPN 证书问题",
                    requester_id="user_emp_1",
                    status="ANSWERED",
                    current_node="answer",
                    created_at=now - timedelta(minutes=10),
                    updated_at=now - timedelta(minutes=8),
                ),
                Case(
                    id=ids["ticket_case"],
                    title="打印机故障",
                    requester_id="user_emp_1",
                    status="TICKET_OPEN",
                    current_node="ticket",
                    ticket_id=ids["ticket"],
                    created_at=now - timedelta(minutes=30),
                    updated_at=now - timedelta(minutes=5),
                ),
                Case(
                    id=ids["approval_case"],
                    title="账户权限审批",
                    requester_id="user_emp_1",
                    status="AWAITING_APPROVAL",
                    current_node="await_approval",
                    created_at=now - timedelta(minutes=20),
                    updated_at=now - timedelta(minutes=2),
                ),
                Case(
                    id=ids["failed_case"],
                    title="工具执行失败",
                    requester_id="user_emp_1",
                    status="AWAITING_APPROVAL",
                    current_node="execution_failed",
                    created_at=now - timedelta(minutes=18),
                    updated_at=now - timedelta(minutes=1),
                ),
                Case(
                    id=ids["old_case"],
                    title="十天前的已解决 Case",
                    requester_id="user_emp_1",
                    status="ANSWERED",
                    current_node="answer",
                    created_at=now - timedelta(days=10),
                    updated_at=now - timedelta(days=10),
                ),
                Ticket(
                    id=ids["ticket"],
                    case_id=ids["ticket_case"],
                    title="打印机报错 0x0000011b",
                    description="Windows 11 打印失败",
                    category="hardware",
                    priority="P2",
                    priority_reason="影响办公",
                    fields={"environment": "Windows 11"},
                    missing_fields=[],
                    status="OPEN",
                    version=2,
                    created_at=now - timedelta(minutes=29),
                    updated_at=now - timedelta(minutes=5),
                ),
                ActionRequest(
                    id=ids["approved_action"],
                    case_id=ids["approval_case"],
                    tool_name="reset_vpn_certificate",
                    tool_label="重置 VPN 证书",
                    tool_type="WRITE",
                    risk_level="HIGH",
                    args={"user_id": "user_emp_1"},
                    args_hash="sha256:approved",
                    rationale="测试审批样本",
                    impact="仅影响当前用户",
                    verification_plan="执行后复核",
                    rollback_plan="人工回滚",
                    evidence_ids=[],
                    status="SUCCEEDED",
                    requested_by_id="user_emp_1",
                    idempotency_key=new_id("idem"),
                    expires_at=now + timedelta(hours=1),
                    created_at=now - timedelta(minutes=20),
                    updated_at=now - timedelta(minutes=8),
                ),
                ActionRequest(
                    id=ids["rejected_action"],
                    case_id=ids["approval_case"],
                    tool_name="grant_app_access",
                    tool_label="开通应用权限",
                    tool_type="WRITE",
                    risk_level="MEDIUM",
                    args={"user_id": "user_emp_1", "app_name": "Visio"},
                    args_hash="sha256:rejected",
                    rationale="测试拒绝样本",
                    impact="仅影响当前用户",
                    verification_plan="执行后复核",
                    rollback_plan="人工回滚",
                    evidence_ids=[],
                    status="REJECTED",
                    requested_by_id="user_emp_1",
                    idempotency_key=new_id("idem"),
                    expires_at=now + timedelta(hours=1),
                    created_at=now - timedelta(minutes=18),
                    updated_at=now - timedelta(minutes=13),
                ),
                ActionRequest(
                    id=ids["failed_action"],
                    case_id=ids["failed_case"],
                    tool_name="grant_app_access",
                    tool_label="开通应用权限",
                    tool_type="WRITE",
                    risk_level="MEDIUM",
                    args={"user_id": "user_emp_1", "app_name": "Jira"},
                    args_hash="sha256:failed",
                    rationale="测试失败样本",
                    impact="仅影响当前用户",
                    verification_plan="执行后复核",
                    rollback_plan="人工回滚",
                    evidence_ids=[],
                    status="FAILED",
                    requested_by_id="user_emp_1",
                    idempotency_key=new_id("idem"),
                    expires_at=now + timedelta(hours=1),
                    created_at=now - timedelta(minutes=18),
                    updated_at=now - timedelta(minutes=1),
                ),
                Approval(
                    id=new_id("approval"),
                    action_id=ids["approved_action"],
                    status="APPROVED",
                    args_hash="sha256:approved",
                    approver_id="user_approver",
                    decision_reason="影响范围确认",
                    requested_at=now - timedelta(minutes=20),
                    expires_at=now + timedelta(minutes=20),
                    decided_at=now - timedelta(minutes=10),
                ),
                Approval(
                    id=new_id("approval"),
                    action_id=ids["rejected_action"],
                    status="REJECTED",
                    args_hash="sha256:rejected",
                    approver_id="user_approver",
                    decision_reason="权限不足",
                    requested_at=now - timedelta(minutes=18),
                    expires_at=now + timedelta(minutes=20),
                    decided_at=now - timedelta(minutes=13),
                ),
                ToolExecution(
                    id=ids["execution"],
                    action_id=ids["approved_action"],
                    tool_name="reset_vpn_certificate",
                    status="SUCCEEDED",
                    idempotency_key=new_id("execidem"),
                    args_hash="sha256:approved",
                    output={"ok": True},
                    result_summary="证书已重置",
                    verification={"passed": True},
                    request_id="m4-dashboard",
                    started_at=now - timedelta(seconds=1),
                    finished_at=now,
                ),
            ]
        )
        await ensure_eval_metadata(db, owner_id="user_eval")
        dataset = (
            await db.execute(
                select(EvalDataset).where(EvalDataset.dataset_type == "security")
            )
        ).scalar_one()
        db.add(
            EvalRun(
                id=new_id("evalrun"),
                dataset_id=dataset.id,
                label="看板评估趋势",
                prompt_version="m4-safe-v2-candidate",
                model_config={"provider": "local-rules"},
                retrieval_config={"limit": 3},
                run_config={"mode": "single_config"},
                status="COMPLETED",
                metrics={
                    "pass_rate": 0.9,
                    "unauthorized_refusal_rate": 0.95,
                    "sample_size": 15,
                },
                sample_count=15,
                created_by_id="user_eval",
            )
        )
        db.add_all(
            [
                AuditEvent(
                    id=new_id("audit"),
                    case_id=ids["ticket_case"],
                    actor_id="user_support_1",
                    actor_role="support",
                    event_type="ticket.updated",
                    payload={"ticket_id": ids["ticket"], "changed_fields": ["priority"]},
                    request_id="m4-dashboard-1",
                    result="success",
                    created_at=now - timedelta(minutes=6),
                ),
                AuditEvent(
                    id=new_id("audit"),
                    case_id=ids["ticket_case"],
                    actor_id="user_support_1",
                    actor_role="support",
                    event_type="ticket.updated",
                    payload={"ticket_id": ids["ticket"], "changed_fields": ["environment"]},
                    request_id="m4-dashboard-2",
                    result="success",
                    created_at=now - timedelta(minutes=4),
                ),
                AuditEvent(
                    id=new_id("audit"),
                    case_id=ids["ticket_case"],
                    actor_id="user_support_1",
                    actor_role="support",
                    event_type="ticket.updated",
                    payload={"ticket_id": ids["ticket"], "kind": "note"},
                    request_id="m4-dashboard-3",
                    result="success",
                    created_at=now - timedelta(minutes=3),
                ),
                AuditEvent(
                    id=new_id("audit"),
                    case_id=ids["approval_case"],
                    actor_id="user_approver",
                    actor_role="approver",
                    event_type="tool.duplicate_blocked",
                    payload={"approval_id": "approval_repeat"},
                    request_id="m4-dashboard-4",
                    result="success",
                    created_at=now - timedelta(minutes=2),
                ),
                AuditEvent(
                    id=new_id("audit"),
                    case_id=ids["knowledge_case"],
                    actor_id="user_emp_1",
                    actor_role="employee",
                    event_type="answer.generated",
                    payload={"latency_ms": 120, "cost_usd": 0.00012},
                    request_id="m4-dashboard-5",
                    result="success",
                    created_at=now - timedelta(minutes=9),
                ),
                AuditEvent(
                    id=new_id("audit"),
                    case_id=ids["knowledge_case"],
                    actor_id="user_emp_1",
                    actor_role="employee",
                    event_type="retrieval.completed",
                    payload={"latency_ms": 40},
                    request_id="m4-dashboard-6",
                    result="success",
                    created_at=now - timedelta(minutes=9),
                ),
                AuditEvent(
                    id=new_id("audit"),
                    actor_id="user_admin",
                    actor_role="admin",
                    event_type="redaction.check",
                    payload={
                        "password": "super-secret",
                        "nested": {"api_key": "key-value", "safe": "visible"},
                        "long": "x" * 600,
                    },
                    request_id="redaction-check-1",
                    result="success",
                    created_at=now - timedelta(minutes=1),
                ),
                AuditEvent(
                    id=new_id("audit"),
                    actor_id="user_admin",
                    actor_role="admin",
                    event_type="redaction.check",
                    payload={"token": "token-value", "safe": "visible"},
                    request_id="redaction-check-2",
                    result="success",
                    created_at=now,
                ),
            ]
        )
        await db.commit()
    return ids


async def test_dashboard_audit_and_role_contracts(client: AsyncClient):
    await seed_dashboard_data()
    await login(client, "audit@example.test")

    seven = await client.get("/api/dashboard?range=7d")
    assert seven.status_code == 200, seven.text
    week = seven.json()
    assert week["range"] == "7d"
    assert week["cases_total"] == 4
    assert week["knowledge_resolution_rate"] == 0.25
    assert week["ticket_rate"] == 0.25
    assert week["approval_requests"] == 2
    assert week["approval_rejected"] == 1
    assert week["approval_failed"] == 1
    assert week["manual_correction_rate"] == 1.0
    assert week["approval_pass_rate"] == 0.5
    assert week["avg_approval_wait_minutes"] == 7.5
    assert week["duplicate_execution_blocked"] == 1
    assert week["avg_answer_latency_ms"] == 120
    assert week["avg_retrieval_latency_ms"] == 40
    assert week["avg_tool_latency_ms"] == 1000
    assert week["category_distribution"][0]["key"] == "hardware"
    assert week["priority_distribution"][0]["key"] == "P2"
    assert week["sample_sizes"]["cases_total"] == 4
    assert week["sample_sizes"]["manual_correction_rate"] == 1
    assert week["sample_sizes"]["avg_answer_latency_ms"] == 1
    assert week["eval_trend"][0]["sample_size"] == 15
    assert week["methodology"]["manual_correction"]

    month = await client.get("/api/dashboard?range=30d")
    assert month.status_code == 200
    assert month.json()["cases_total"] == 5

    audit = await client.get("/api/audit/events?q=redaction-check&limit=1&offset=1")
    assert audit.status_code == 200, audit.text
    audit_body = audit.json()
    assert audit_body["total"] == 2
    assert len(audit_body["items"]) == 1
    payload = audit_body["items"][0]["payload"]
    assert payload["password"] != "super-secret"
    assert payload["nested"]["api_key"] != "key-value"
    assert payload["nested"]["safe"] == "visible"
    assert len(payload["long"]) <= 501
    assert audit_body["event_types"] == ["redaction.check"]

    assert (await client.get("/api/eval/datasets")).status_code == 403
    assert (await client.get("/api/admin/settings")).status_code == 403

    await switch_user(client, "eval@example.test")
    assert (await client.get("/api/eval/datasets")).status_code == 200
    assert (await client.get("/api/dashboard")).status_code == 403
    assert (await client.get("/api/audit/events")).status_code == 403
    assert (await client.get("/api/admin/settings")).status_code == 403

    await switch_user(client, "support1@example.test")
    assert (await client.get("/api/dashboard")).status_code == 200
    assert (await client.get("/api/audit/events")).status_code == 403

    await switch_user(client, "admin@example.test")
    assert (await client.get("/api/dashboard")).status_code == 200
    assert (await client.get("/api/audit/events")).status_code == 200
    assert (await client.get("/api/eval/datasets")).status_code == 200
    assert (await client.get("/api/admin/settings")).status_code == 200


async def test_feedback_is_candidate_only_and_audited(client: AsyncClient):
    await login(client, "emp1@example.test")
    case = await create_case(client, "VPN 证书无效")
    events = await send_message(client, case["id"], "VPN 提示证书无效，应该怎么处理？")
    assert any(name == "citation" for name, _ in events)
    assistant = (await client.get(f"/api/cases/{case['id']}/messages")).json()["items"][-1]

    async with TestSession() as db:
        before_documents = len(
            (await db.execute(select(KnowledgeDocument.id))).scalars().all()
        )

    negative = await client.post(
        f"/api/messages/{assistant['id']}/feedback",
        json={"rating": "unhelpful", "reason": "missing_steps", "comment": "缺少证书下载步骤"},
        headers=csrf_headers(client),
    )
    assert negative.status_code == 200, negative.text
    feedback_id = negative.json()["id"]
    assert len(feedback_id) <= 40
    assert negative.json()["reason"] == "missing_steps"

    positive = await client.post(
        f"/api/messages/{assistant['id']}/feedback",
        json={"rating": "helpful", "comment": "已解决问题"},
        headers=csrf_headers(client),
    )
    assert positive.status_code == 200
    assert positive.json()["id"] == feedback_id
    assert positive.json()["reason"] is None

    async with TestSession() as db:
        rows = (await db.execute(select(MessageFeedback))).scalars().all()
        assert len(rows) == 1
        assert rows[0].rating == "helpful"
        after_documents = len(
            (await db.execute(select(KnowledgeDocument.id))).scalars().all()
        )
        assert after_documents == before_documents

    async with TestSession() as db:
        feedback_events = list(
            (
                await db.execute(
                    select(AuditEvent).where(AuditEvent.event_type == "feedback.submitted")
                )
            ).scalars().all()
        )
    assert len(feedback_events) == 2
    assert all(item.payload["candidate_only"] is True for item in feedback_events)

    await switch_user(client, "emp2@example.test")
    denied = await client.post(
        f"/api/messages/{assistant['id']}/feedback",
        json={"rating": "helpful"},
        headers=csrf_headers(client),
    )
    assert denied.status_code == 404


async def test_admin_settings_prompt_and_runtime_affect_business(client: AsyncClient):
    await login(client, "admin@example.test")
    settings = await client.get("/api/admin/settings")
    assert settings.status_code == 200, settings.text
    body = settings.json()
    assert body["runtime_config"]["retrieval_min_score"] == 0.2
    assert body["taxonomy"]["roles"]
    assert body["prompts"]

    runtime = body["runtime_config"]
    runtime.update(
        {
            "retrieval_limit": 1,
            "max_context_chunks": 1,
            "retrieval_min_score": 0.0,
            "max_steps": 3,
            "approval_ttl_seconds": 120,
            "evaluation_regression_threshold": 0.1,
            "answer_style": "detailed",
        }
    )
    updated_runtime = await client.put(
        "/api/admin/runtime-config", json=runtime, headers=csrf_headers(client)
    )
    assert updated_runtime.status_code == 200, updated_runtime.text
    assert updated_runtime.json()["retrieval_limit"] == 1

    user_update = await client.patch(
        "/api/admin/users/user_support_2",
        json={"role": "evaluator", "department": "质量与评估", "is_active": True},
        headers=csrf_headers(client),
    )
    assert user_update.status_code == 200, user_update.text
    assert user_update.json()["role"] == "evaluator"

    self_demotion = await client.patch(
        "/api/admin/users/user_admin",
        json={"role": "employee"},
        headers=csrf_headers(client),
    )
    assert self_demotion.status_code == 409

    prompt = await client.post(
        "/api/admin/prompts",
        json={
            "version": "m4-acceptance-v1",
            "name": "M4 验收集 Prompt",
            "system_prompt": "仅依据检索证据回答，写操作必须审批。",
            "activate": True,
        },
        headers=csrf_headers(client),
    )
    assert prompt.status_code == 201, prompt.text
    prompts = (await client.get("/api/admin/prompts")).json()["items"]
    assert [item["version"] for item in prompts if item["is_active"]] == ["m4-acceptance-v1"]

    audit = await client.get("/api/audit/events?event_type=config.changed")
    assert audit.status_code == 200
    assert audit.json()["total"] >= 3

    await switch_user(client, "emp1@example.test")
    case = await create_case(client, "VPN 证书过期")
    events = await send_message(client, case["id"], "我的 VPN 证书过期了，帮我重置证书")
    action_event = next(data for name, data in events if name == "action")
    citations = [data for name, data in events if name == "citation"]
    assert len(citations) == 1

    approval = action_event["approval"]
    requested_at = datetime.fromisoformat(approval["requested_at"].replace("Z", "+00:00"))
    expires_at = datetime.fromisoformat(approval["expires_at"].replace("Z", "+00:00"))
    ttl = (expires_at - requested_at).total_seconds()
    assert 110 <= ttl <= 130

    async with TestSession() as db:
        retrieval = (
            await db.execute(
                select(AuditEvent).where(
                    AuditEvent.case_id == case["id"],
                    AuditEvent.event_type == "retrieval.completed",
                )
            )
        ).scalar_one()
        answer = (
            await db.execute(
                select(AuditEvent).where(
                    AuditEvent.case_id == case["id"],
                    AuditEvent.event_type == "answer.generated",
                )
            )
        ).scalar_one()
    assert retrieval.payload["retrieval_limit"] == 1
    assert retrieval.payload["max_context_chunks"] == 1
    message = (
        await client.get(f"/api/cases/{case['id']}/messages")
    ).json()["items"][-1]
    assert "依据摘要" in message["content"]
    assert len(message["citations"]) == 1
    assert answer.payload["token_count"] > 0


async def test_demo_reset_requires_confirmation_and_reseeds_defaults(client: AsyncClient):
    await login(client, "admin@example.test")
    await client.get("/api/eval/datasets")
    denied = await client.post(
        "/api/admin/reset-demo",
        json={"confirmation": "reset"},
        headers=csrf_headers(client),
    )
    assert denied.status_code == 422
    assert denied.json()["error"]["code"] == "CONFIRMATION_REQUIRED"

    response = await client.post(
        "/api/admin/reset-demo",
        json={"confirmation": "RESET-DEMO"},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["reseeded_documents"] == 12
    assert body["deleted"]["eval_datasets"] == 3
    assert body["deleted"]["prompt_versions"] >= 2
    assert body["audit_event_id"]

    datasets = (await client.get("/api/eval/datasets")).json()["items"]
    assert sorted(item["item_count"] for item in datasets) == [15, 40, 80]
    documents = (await client.get("/api/knowledge/documents")).json()["items"]
    assert len(documents) == 12
    audit = await client.get("/api/audit/events?event_type=demo.reset")
    assert audit.status_code == 200
    assert audit.json()["total"] == 1
