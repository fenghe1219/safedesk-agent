import json
import re
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

from httpx import AsyncClient
from sqlalchemy import delete

from app.core.security import utcnow
from app.models.action import ActionRequest, Approval, WorkflowCheckpoint
from app.models.case import Case
from app.services.action_service import _scope_allows, detect_action_intent
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


async def create_case(client: AsyncClient, title: str = "VPN 证书过期"):
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


async def request_vpn_action(client: AsyncClient, *, email: str = "emp1@example.test"):
    await login(client, email)
    case = await create_case(client)
    events = await send_message(
        client, case["id"], "我的 VPN 证书过期了，帮我重置证书"
    )
    action_event = event_data(events, "action")
    assert action_event is not None
    return case, events, action_event


async def switch_user(client: AsyncClient, email: str) -> None:
    await client.post("/api/auth/logout", headers=csrf_headers(client))
    response = await login(client, email)
    assert response.status_code == 200, response.text


def approval_payload(action_event: dict[str, Any], reason: str | None = None) -> dict[str, Any]:
    return {
        "expected_args_hash": action_event["action"]["args_hash"],
        "approval_version": action_event["approval"]["version"],
        "reason": reason,
    }


async def timeline_types(client: AsyncClient, case_id: str) -> list[str]:
    response = await client.get(f"/api/cases/{case_id}/timeline")
    assert response.status_code == 200
    return [item["event_type"] for item in response.json()["items"]]


def test_grant_intent_requires_permission_language():
    case = Case(id="case_intent", title="权限申请", requester_id="user_emp_1")
    intent = detect_action_intent("申请 Visio 权限", case)
    assert intent is not None
    assert intent.tool_name == "grant_app_access"
    assert intent.args["app_name"] == "Visio"
    assert detect_action_intent("申请安装 Visio", case) is None


def test_wildcard_approval_scope_matches_all_tools_and_departments():
    user = SimpleNamespace(
        approval_scopes={"tools": ["*"], "departments": ["*"]}
    )
    action = SimpleNamespace(tool_name="reset_vpn_certificate")
    requester = SimpleNamespace(department="产品部")
    assert _scope_allows(user, action, requester) is True


async def test_action_proposal_uses_read_tool_and_creates_checkpoints(client: AsyncClient):
    await login(client, "emp1@example.test")
    case = await create_case(client)
    events = await send_message(
        client, case["id"], "我的 VPN 证书过期了，帮我重置证书"
    )
    action_event = event_data(events, "action")
    done = event_data(events, "done")
    assert action_event is not None
    assert done is not None
    assert action_event["action"]["tool_name"] == "reset_vpn_certificate"
    assert action_event["approval"]["status"] == "PENDING"
    assert action_event["case"]["status"] == "AWAITING_APPROVAL"
    assert done["action_id"] == action_event["action"]["id"]
    assert done["case_status"] == "AWAITING_APPROVAL"
    assert "ticket_id" not in done

    detail = (await client.get(f"/api/cases/{case['id']}/action")).json()
    assert detail["status"] == "AWAITING_APPROVAL"
    assert detail["approval"]["status"] == "PENDING"
    assert detail["evidence_ids"]
    assert detail["permissions"]["can_decide"] is False

    checkpoints = (await client.get(f"/api/cases/{case['id']}/checkpoints")).json()["items"]
    nodes = [item["node"] for item in checkpoints]
    assert "propose_action" in nodes
    assert "await_approval" in nodes

    types = await timeline_types(client, case["id"])
    assert "tool.read_executed" in types
    assert "action.proposed" in types
    assert "approval.requested" in types

    denied = await client.get("/api/approvals")
    assert denied.status_code == 403

    await switch_user(client, "approver@example.test")
    approvals = (await client.get("/api/approvals")).json()["items"]
    assert len(approvals) == 1
    assert approvals[0]["id"] == action_event["approval"]["id"]
    assert approvals[0]["can_decide"] is True


async def test_approval_executes_once_and_repeat_is_idempotent(client: AsyncClient):
    _, _, action_event = await request_vpn_action(client)
    await switch_user(client, "approver@example.test")
    payload = approval_payload(action_event, "已核对影响范围")

    response = await client.post(
        f"/api/approvals/{action_event['approval']['id']}/approve",
        json=payload,
        headers=csrf_headers(client),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["case"]["status"] == "RESOLVED"
    assert body["action"]["status"] == "SUCCEEDED"
    assert body["execution"]["status"] == "SUCCEEDED"
    execution_id = body["execution"]["id"]

    repeated = await client.post(
        f"/api/approvals/{action_event['approval']['id']}/approve",
        json=payload,
        headers=csrf_headers(client),
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["execution"]["id"] == execution_id

    types = await timeline_types(client, action_event["case"]["id"])
    assert types.count("tool.executed") == 1
    assert "action.verified" in types
    assert "case.resolved" in types
    checkpoints = (
        await client.get(f"/api/cases/{action_event['case']['id']}/checkpoints")
    ).json()["items"]
    nodes = [item["node"] for item in checkpoints]
    assert "approval_decided" in nodes
    assert "verify_action" in nodes
    assert "resolved" in nodes


async def test_employee_and_admin_cannot_decide(client: AsyncClient):
    _, _, action_event = await request_vpn_action(client)
    payload = approval_payload(action_event)
    employee_response = await client.post(
        f"/api/approvals/{action_event['approval']['id']}/approve",
        json=payload,
        headers=csrf_headers(client),
    )
    assert employee_response.status_code == 403

    await switch_user(client, "admin@example.test")
    admin_response = await client.post(
        f"/api/approvals/{action_event['approval']['id']}/approve",
        json=payload,
        headers=csrf_headers(client),
    )
    assert admin_response.status_code == 403


async def test_requester_cannot_approve_own_action(client: AsyncClient):
    _, _, action_event = await request_vpn_action(client, email="approver@example.test")
    response = await client.post(
        f"/api/approvals/{action_event['approval']['id']}/approve",
        json=approval_payload(action_event),
        headers=csrf_headers(client),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SELF_APPROVAL_FORBIDDEN"


async def test_tampered_args_hash_is_rejected(client: AsyncClient):
    _, _, action_event = await request_vpn_action(client)
    async with TestSession() as db:
        action = await db.get(ActionRequest, action_event["action"]["id"])
        assert action is not None
        action.args_hash = "sha256:tampered"
        await db.commit()

    await switch_user(client, "approver@example.test")
    response = await client.post(
        f"/api/approvals/{action_event['approval']['id']}/approve",
        json=approval_payload(action_event),
        headers=csrf_headers(client),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TYPE_CONFLICT"


async def test_reject_requires_reason_and_never_executes(client: AsyncClient):
    _, _, action_event = await request_vpn_action(client)
    await switch_user(client, "approver@example.test")
    url = f"/api/approvals/{action_event['approval']['id']}/reject"
    invalid = await client.post(
        url,
        json={"approval_version": action_event["approval"]["version"], "reason": ""},
        headers=csrf_headers(client),
    )
    assert invalid.status_code == 422

    response = await client.post(
        url,
        json={
            "approval_version": action_event["approval"]["version"],
            "reason": "影响范围说明不足",
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["action"]["status"] == "REJECTED"
    assert body["case"]["status"] == "REJECTED"
    assert body["execution"] is None
    types = await timeline_types(client, action_event["case"]["id"])
    assert "approval.rejected" in types
    assert "tool.executed" not in types


async def test_expired_approval_cannot_execute(client: AsyncClient):
    _, _, action_event = await request_vpn_action(client)
    expired_at = utcnow() - timedelta(seconds=1)
    async with TestSession() as db:
        action = await db.get(ActionRequest, action_event["action"]["id"])
        approval = await db.get(Approval, action_event["approval"]["id"])
        assert action is not None and approval is not None
        action.expires_at = expired_at
        approval.expires_at = expired_at
        await db.commit()

    await switch_user(client, "approver@example.test")
    response = await client.post(
        f"/api/approvals/{action_event['approval']['id']}/approve",
        json=approval_payload(action_event),
        headers=csrf_headers(client),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "APPROVAL_EXPIRED"
    detail = (await client.get(f"/api/cases/{action_event['case']['id']}/action")).json()
    assert detail["status"] == "EXPIRED"
    assert detail["approval"]["status"] == "EXPIRED"
    assert detail["execution"] is None


async def test_disabled_tool_blocks_execution(client: AsyncClient):
    _, _, action_event = await request_vpn_action(client)
    await switch_user(client, "admin@example.test")
    updated = await client.patch(
        "/api/admin/tools/reset_vpn_certificate",
        json={"enabled": False},
        headers=csrf_headers(client),
    )
    assert updated.status_code == 200, updated.text

    await switch_user(client, "approver@example.test")
    response = await client.post(
        f"/api/approvals/{action_event['approval']['id']}/approve",
        json=approval_payload(action_event),
        headers=csrf_headers(client),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TOOL_DISABLED"
    detail = (await client.get(f"/api/cases/{action_event['case']['id']}/action")).json()
    assert detail["execution"] is None


async def test_kill_switch_blocks_execution(client: AsyncClient):
    _, _, action_event = await request_vpn_action(client)
    await switch_user(client, "admin@example.test")
    switched = await client.put(
        "/api/admin/kill-switch",
        json={"enabled": True, "reason": "演练"},
        headers=csrf_headers(client),
    )
    assert switched.status_code == 200, switched.text

    await switch_user(client, "approver@example.test")
    response = await client.post(
        f"/api/approvals/{action_event['approval']['id']}/approve",
        json=approval_payload(action_event),
        headers=csrf_headers(client),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "KILL_SWITCH_ENABLED"


async def test_closed_case_blocks_execution(client: AsyncClient):
    _, _, action_event = await request_vpn_action(client)
    async with TestSession() as db:
        case = await db.get(Case, action_event["case"]["id"])
        assert case is not None
        case.status = "CANCELLED"
        await db.commit()

    await switch_user(client, "approver@example.test")
    response = await client.post(
        f"/api/approvals/{action_event['approval']['id']}/approve",
        json=approval_payload(action_event),
        headers=csrf_headers(client),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CASE_CLOSED"
    detail = (await client.get(f"/api/cases/{action_event['case']['id']}/action")).json()
    assert detail["execution"] is None


async def test_mock_failure_returns_failed_state(client: AsyncClient):
    _, _, action_event = await request_vpn_action(client)
    await switch_user(client, "admin@example.test")
    updated = await client.patch(
        "/api/admin/tools/reset_vpn_certificate",
        json={"mock_mode": "fail"},
        headers=csrf_headers(client),
    )
    assert updated.status_code == 200, updated.text

    await switch_user(client, "approver@example.test")
    response = await client.post(
        f"/api/approvals/{action_event['approval']['id']}/approve",
        json=approval_payload(action_event),
        headers=csrf_headers(client),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["action"]["status"] == "FAILED"
    assert body["case"]["status"] == "FAILED"
    assert body["execution"]["status"] == "FAILED"
    assert body["execution"]["error_code"] == "TOOL_FAILED"


async def test_case_action_recovers_checkpoint_from_business_state(client: AsyncClient):
    case, _, _ = await request_vpn_action(client)
    async with TestSession() as db:
        await db.execute(
            delete(WorkflowCheckpoint).where(WorkflowCheckpoint.case_id == case["id"])
        )
        await db.commit()

    response = await client.get(f"/api/cases/{case['id']}/action")
    assert response.status_code == 200, response.text
    checkpoints = (await client.get(f"/api/cases/{case['id']}/checkpoints")).json()["items"]
    assert checkpoints
    assert checkpoints[-1]["node"] == "await_approval"
    assert checkpoints[-1]["status"] == "recovered"
    assert checkpoints[-1]["state"]["recovered_from_business_state"] is True


async def test_no_public_write_tool_execute_endpoint(client: AsyncClient):
    await login(client, "emp1@example.test")
    get_response = await client.get("/api/tools/execute")
    post_response = await client.post(
        "/api/tools/execute", json={}, headers=csrf_headers(client)
    )
    assert get_response.status_code == 404
    assert post_response.status_code == 404
