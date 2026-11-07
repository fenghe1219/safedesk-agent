from __future__ import annotations

import json
import re
from collections import deque
from typing import Any

import httpx
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.models.action import ActionRequest, Approval, ToolExecution
from app.models.audit import AuditEvent
from app.models.case import Case
from app.models.memory import MemoryEntry
from app.services import llm as llm_module
from app.services.memory import local_query_rewrite
from tests.conftest import TestSession, csrf_headers, login


def sse_events(body: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for frame in body.split("\n\n"):
        event = re.search(r"^event: (.+)$", frame, re.MULTILINE)
        data = re.search(r"^data: (.+)$", frame, re.MULTILINE)
        if event and data:
            events.append((event.group(1), json.loads(data.group(1))))
    return events


def event_data(
    events: list[tuple[str, dict[str, Any]]], name: str
) -> dict[str, Any] | None:
    for event_name, data in events:
        if event_name == name:
            return data
    return None


async def create_case(client: AsyncClient, title: str = "VPN 证书无效") -> dict[str, Any]:
    response = await client.post(
        "/api/cases", json={"title": title}, headers=csrf_headers(client)
    )
    assert response.status_code == 201, response.text
    return response.json()


async def send_message(client: AsyncClient, case_id: str, content: str):
    response = await client.post(
        f"/api/cases/{case_id}/messages",
        json={"content": content},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200, response.text
    return sse_events(response.text)


def install_mock_llm(
    monkeypatch, responses: list[str], *, agent_status: int = 200
) -> list[dict[str, Any]]:
    queue = deque(responses)
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        messages = payload["messages"]
        if "检索查询改写器" in messages[0]["content"]:
            current = messages[1]["content"].rsplit("当前问题：", 1)[-1].strip()
            content = json.dumps({"query": current}, ensure_ascii=False)
        elif agent_status != 200:
            return httpx.Response(
                agent_status, json={"error": {"message": "upstream unavailable"}}
            )
        else:
            assert queue, "mock LLM received more calls than expected"
            content = queue.popleft()
        return httpx.Response(
            200,
            json={
                "model": payload["model"],
                "choices": [{"message": {"role": "assistant", "content": content}}],
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 40,
                    "total_tokens": 160,
                },
            },
        )

    monkeypatch.setattr(settings, "llm_provider", "openai_compatible")
    monkeypatch.setattr(settings, "llm_base_url", "http://llm.test/v1")
    monkeypatch.setattr(settings, "llm_model", "test-agent-model")
    monkeypatch.setattr(settings, "llm_input_cost_per_million", 1.0)
    monkeypatch.setattr(settings, "llm_output_cost_per_million", 2.0)
    monkeypatch.setattr(
        llm_module, "LLM_TRANSPORT", httpx.MockTransport(handler)
    )
    return requests


async def audit_events(case_id: str, event_type: str) -> list[AuditEvent]:
    async with TestSession() as db:
        result = await db.execute(
            select(AuditEvent)
            .where(AuditEvent.case_id == case_id, AuditEvent.event_type == event_type)
            .order_by(AuditEvent.created_at.asc())
        )
        return list(result.scalars().all())


async def test_agent_read_tool_observation_then_cited_answer(
    client: AsyncClient, monkeypatch
):
    requests = install_mock_llm(
        monkeypatch,
        [
            json.dumps(
                {
                    "answer": "我先检查 VPN 状态。",
                    "citation_indices": [],
                    "refused": False,
                    "tool_call": {
                        "name": "get_vpn_status",
                        "arguments": {"user_id": "user_emp_2"},
                        "rationale": "需要确认证书状态",
                    },
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "answer": "证书已过期，请按知识库步骤重新登录并更新证书 [1]。",
                    "citation_indices": [1],
                    "refused": False,
                    "tool_call": None,
                },
                ensure_ascii=False,
            ),
        ],
    )
    await login(client, "emp1@example.test")
    case = await create_case(client)

    events = await send_message(client, case["id"], "我的 VPN 证书无效，帮我看看状态")
    done = event_data(events, "done")
    assert done is not None
    assert done["evidence_count"] >= 1

    messages = (await client.get(f"/api/cases/{case['id']}/messages")).json()["items"]
    assistant = messages[-1]
    assert "证书已过期" in assistant["content"]
    assert assistant["citations"]
    assert assistant["model_version"] == "test-agent-model"

    assert len([item for item in requests if "可用工具" in item["messages"][1]["content"]]) == 2
    observation_message = requests[-1]["messages"][-1]["content"]
    assert '"tool_name": "get_vpn_status"' in observation_message
    assert '"user_id": "user_emp_1"' in observation_message
    assert '"user_id": "user_emp_2"' not in observation_message

    calls = await audit_events(case["id"], "agent.model_call")
    assert len(calls) == 2
    assert all(item.payload["usage_estimated"] is False for item in calls)
    assert (await audit_events(case["id"], "tool.read_executed"))
    assert (await audit_events(case["id"], "agent.completed"))


async def test_agent_write_proposal_creates_approval_but_never_executes(
    client: AsyncClient, monkeypatch
):
    install_mock_llm(
        monkeypatch,
        [
            json.dumps(
                {
                    "answer": "我会提交重置证书的审批请求。",
                    "citation_indices": [],
                    "refused": False,
                    "tool_call": {
                        "name": "reset_vpn_certificate",
                        "arguments": {
                            "user_id": "user_emp_2",
                            "reason": "证书过期，请求重置",
                        },
                        "rationale": "用户明确要求重置证书",
                    },
                },
                ensure_ascii=False,
            )
        ],
    )
    await login(client, "emp1@example.test")
    case = await create_case(client, "VPN 证书过期")

    events = await send_message(
        client, case["id"], "我的 VPN 证书过期了，帮我重置证书"
    )
    action_event = event_data(events, "action")
    assert action_event is not None
    assert action_event["approval"]["status"] == "PENDING"
    assert action_event["case"]["status"] == "AWAITING_APPROVAL"
    assert action_event["action"]["tool_name"] == "reset_vpn_certificate"
    assert action_event["action"]["args"]["user_id"] == "user_emp_1"

    async with TestSession() as db:
        action = await db.get(ActionRequest, action_event["action"]["id"])
        approval = await db.get(Approval, action_event["approval"]["id"])
        executions = list((await db.execute(select(ToolExecution))).scalars().all())
    assert action is not None and action.status == "AWAITING_APPROVAL"
    assert approval is not None and approval.status == "PENDING"
    assert executions == []
    assert not await audit_events(case["id"], "tool.write_executed")


async def test_agent_rejects_unknown_tool_and_records_audit(
    client: AsyncClient, monkeypatch
):
    install_mock_llm(
        monkeypatch,
        [
            json.dumps(
                {
                    "answer": "",
                    "citation_indices": [],
                    "refused": False,
                    "tool_call": {
                        "name": "delete_all_users",
                        "arguments": {"user_id": "user_emp_1"},
                        "rationale": "模型越权提议",
                    },
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "answer": "我无法执行该操作，建议按知识库步骤处理 [1]。",
                    "citation_indices": [1],
                    "refused": False,
                    "tool_call": None,
                },
                ensure_ascii=False,
            ),
        ],
    )
    await login(client, "emp1@example.test")
    case = await create_case(client)

    events = await send_message(client, case["id"], "VPN 证书无效，帮我处理")
    messages = (await client.get(f"/api/cases/{case['id']}/messages")).json()["items"]
    assert "无法执行该操作" in messages[-1]["content"]
    assert event_data(events, "action") is None

    rejected = await audit_events(case["id"], "agent.tool_rejected")
    assert len(rejected) == 1
    assert rejected[0].payload["tool_name"] == "delete_all_users"
    assert rejected[0].payload["code"] == "UNKNOWN_TOOL"


async def test_agent_provider_failure_falls_back_to_local_answer(
    client: AsyncClient, monkeypatch
):
    install_mock_llm(monkeypatch, [], agent_status=503)
    await login(client, "emp1@example.test")
    case = await create_case(client)

    events = await send_message(client, case["id"], "VPN 证书无效应该怎么处理？")
    done = event_data(events, "done")
    assert done is not None
    assert done["refused"] is False

    messages = (await client.get(f"/api/cases/{case['id']}/messages")).json()["items"]
    assert messages[-1]["citations"]
    assert messages[-1]["model_version"] == "extractive-rag-v1"

    fallback = await audit_events(case["id"], "agent.fallback")
    assert len(fallback) == 1
    assert fallback[0].payload["reason"] == "LLM_HTTP_ERROR"


async def test_memory_is_scoped_and_deletable(client: AsyncClient):
    await login(client, "emp1@example.test")
    case = await create_case(client, "VPN 证书报错")
    await send_message(
        client,
        case["id"],
        "我的公司电脑是 Windows 11，VPN 报错 0x80072745，还是不行",
    )
    await send_message(client, case["id"], "以后回答请详细一些")

    response = await client.get("/api/memory", params={"case_id": case["id"]})
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    keys = {item["key"]: item for item in items}
    assert "Windows 11" in keys["environment"]["value"]
    assert "0x80072745" in keys["error_message"]["value"]
    assert keys["answer_style"]["scope"] == "USER"
    assert keys["answer_style"]["value"] == "detailed"

    case_entry = keys["environment"]
    await client.post("/api/auth/logout", headers=csrf_headers(client))
    await login(client, "emp2@example.test")
    other = await client.get("/api/memory", params={"case_id": case["id"]})
    assert other.status_code == 200
    assert other.json()["items"] == []
    denied = await client.delete(
        f"/api/memory/{case_entry['id']}", headers=csrf_headers(client)
    )
    assert denied.status_code == 404

    await client.post("/api/auth/logout", headers=csrf_headers(client))
    await login(client, "emp1@example.test")
    deleted = await client.delete(
        f"/api/memory/{case_entry['id']}", headers=csrf_headers(client)
    )
    assert deleted.status_code == 200, deleted.text
    remaining = (
        await client.get("/api/memory", params={"case_id": case["id"]})
    ).json()["items"]
    assert case_entry["id"] not in {item["id"] for item in remaining}


def test_local_query_rewrite_uses_case_memory_for_followup():
    case = Case(id="case_rewrite", title="VPN 证书无效", requester_id="user_emp_1")
    entries = [
        MemoryEntry(
            id="mem_env",
            user_id="user_emp_1",
            case_id="case_rewrite",
            scope="CASE",
            kind="fact",
            key="environment",
            value="Windows 11",
            confidence=0.9,
        )
    ]
    rewritten = local_query_rewrite("还是不行", case=case, entries=entries)
    assert "VPN 证书无效" in rewritten
    assert "Windows 11" in rewritten
    assert rewritten.endswith("还是不行")


async def test_knowledge_ablation_without_retrieval_and_experiment_api(
    client: AsyncClient,
):
    await login(client, "eval@example.test")
    datasets = (await client.get("/api/eval/datasets")).json()["items"]
    knowledge = next(item for item in datasets if item["dataset_type"] == "knowledge")

    response = await client.post(
        "/api/eval/experiments",
        json={
            "dataset_id": knowledge["id"],
            "variants": [
                {
                    "label": "完整 RAG 基线",
                    "model_settings": {
                        "provider": "local-rules",
                        "answer_mode": "local",
                    },
                    "retrieval_config": {"enabled": True, "limit": 3, "min_score": 0},
                },
                {
                    "label": "关闭 RAG 消融",
                    "model_settings": {
                        "provider": "local-rules",
                        "answer_mode": "local",
                    },
                    "retrieval_config": {"enabled": False},
                },
            ],
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["runs"]) == 2
    assert len(body["comparisons"]) == 1
    full_rag, no_rag = body["runs"]
    assert full_rag["status"] == "COMPLETED"
    assert no_rag["status"] == "COMPLETED"
    assert full_rag["retrieval_config"]["enabled"] is True
    assert no_rag["retrieval_config"]["enabled"] is False
    assert full_rag["metrics"]["retrieval_recall_at_k"] > 0
    assert no_rag["metrics"]["retrieval_recall_at_k"] == 0
    assert full_rag["metrics"]["avg_token_count"] > 0
    assert "fallback_rate" in full_rag["metrics"]

    comparison = body["comparisons"][0]
    recall = next(
        item for item in comparison["metrics"] if item["key"] == "retrieval_recall_at_k"
    )
    assert recall["delta"] < 0
    assert recall["regressed"] is True
    assert "retrieval_recall_at_k" in comparison["blocking_metrics"]

    detail = await client.get(f"/api/eval/runs/{no_rag['id']}?result_limit=2")
    assert detail.status_code == 200, detail.text
    sample = detail.json()["results"]["items"][0]
    assert sample["actual"]["rag_enabled"] is False
    assert sample["actual"]["retrieved_titles"] == []
