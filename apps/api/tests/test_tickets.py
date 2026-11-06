import json
import re
from typing import Any

from httpx import AsyncClient

from app.services.triage import asks_for_ticket, build_triage
from tests.conftest import csrf_headers, login

TICKET_FIELD_KEYS = (
    "title",
    "description",
    "category",
    "priority",
    "priority_reason",
    "affected_system",
    "environment",
    "error_message",
    "urgency_reason",
    "suggested_assignee_id",
)


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


async def create_case(client: AsyncClient, title: str = "打印机故障"):
    response = await client.post(
        "/api/cases", json={"title": title}, headers=csrf_headers(client)
    )
    assert response.status_code == 201
    return response.json()


async def send_message(client: AsyncClient, case_id: str, content: str):
    response = await client.post(
        f"/api/cases/{case_id}/messages",
        json={"content": content},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    return sse_events(response.text)


def fields_from_draft(draft: dict[str, Any]) -> dict[str, Any]:
    return {key: draft[key] for key in TICKET_FIELD_KEYS}


async def create_confirmed_ticket(client: AsyncClient) -> dict[str, Any]:
    await login(client, "emp1@example.test")
    case = await create_case(client)
    events = await send_message(
        client,
        case["id"],
        "打印机报错 0x0000011b，Windows 11，帮我建个工单",
    )
    draft = event_data(events, "ticket_draft")
    assert draft is not None
    await client.post("/api/auth/logout", headers=csrf_headers(client))

    await login(client, "support1@example.test")
    response = await client.post(
        "/api/tickets",
        json={
            "case_id": case["id"],
            "draft_version": draft["version"],
            "fields": fields_from_draft(draft),
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_ambiguous_ticket_request_asks_followup_then_drafts(client: AsyncClient):
    await login(client, "emp1@example.test")
    case = await create_case(client, "打印机坏了")

    events = await send_message(client, case["id"], "打印机坏了，帮我建个工单")
    names = [name for name, _ in events]
    assert "ticket_draft" not in names
    status = event_data(events, "status")
    assert status is not None
    assert status["case_status"] == "NEEDS_INPUT"
    assert (await client.get(f"/api/cases/{case['id']}/ticket-draft")).status_code == 404

    messages = (await client.get(f"/api/cases/{case['id']}/messages")).json()["items"]
    assert "补充" in messages[-1]["content"]
    assert "操作系统" in messages[-1]["content"]

    case_detail = (await client.get(f"/api/cases/{case['id']}")).json()
    assert case_detail["status"] == "NEEDS_INPUT"
    assert case_detail["ticket_id"] is None
    timeline = (await client.get(f"/api/cases/{case['id']}/timeline")).json()["items"]
    assert "ticket.drafted" not in [event["event_type"] for event in timeline]

    events = await send_message(client, case["id"], "Windows 11，报错 0x0000011b")
    draft = event_data(events, "ticket_draft")
    assert draft is not None
    assert draft["status"] == "DRAFT"
    assert draft["category"] == "hardware"
    assert draft["priority"] == "P2"
    assert draft["missing_fields"] == []
    assert draft["suggested_assignee_id"] in {"user_support_1", "user_support_2"}
    done = event_data(events, "done")
    assert done is not None
    assert done["case_status"] == "TICKET_DRAFT"
    assert done["ticket_id"] == draft["ticket_id"]

    case_detail = (await client.get(f"/api/cases/{case['id']}")).json()
    assert case_detail["status"] == "TICKET_DRAFT"
    assert case_detail["ticket_id"] is None
    stored_draft = (await client.get(f"/api/cases/{case['id']}/ticket-draft")).json()
    assert stored_draft["id"] == draft["ticket_id"]
    assert stored_draft["status"] == "DRAFT"
    assert (await client.get("/api/tickets")).json()["items"] == []


async def test_confirm_draft_creates_ticket_and_links_case(client: AsyncClient):
    await login(client, "emp1@example.test")
    case = await create_case(client)
    events = await send_message(
        client,
        case["id"],
        "打印机报错 0x0000011b，Windows 11，帮我建个工单",
    )
    draft = event_data(events, "ticket_draft")
    assert draft is not None
    await client.post("/api/auth/logout", headers=csrf_headers(client))

    await login(client, "support1@example.test")
    response = await client.post(
        "/api/tickets",
        json={
            "case_id": case["id"],
            "draft_version": draft["version"],
            "fields": fields_from_draft(draft),
        },
        headers=csrf_headers(client),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    ticket = body["ticket"]
    assert ticket["status"] == "OPEN"
    assert ticket["status_label"] == "待处理"
    assert ticket["requester_id"] == "user_emp_1"
    assert ticket["requester_name"] == "员工一"
    assert ticket["suggested_assignee_id"] in {"user_support_1", "user_support_2"}
    assert body["case"]["status"] == "TICKET_OPEN"
    assert body["case"]["ticket_id"] == ticket["id"]

    duplicate = await client.post(
        "/api/tickets",
        json={
            "case_id": case["id"],
            "draft_version": draft["version"],
            "fields": fields_from_draft(draft),
        },
        headers=csrf_headers(client),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "INVALID_STATE"

    await client.post("/api/auth/logout", headers=csrf_headers(client))
    await login(client, "emp1@example.test")
    case_detail = (await client.get(f"/api/cases/{case['id']}")).json()
    assert case_detail["status"] == "TICKET_OPEN"
    assert case_detail["ticket_id"] == ticket["id"]
    detail = await client.get(f"/api/tickets/{ticket['id']}")
    assert detail.status_code == 200
    assert detail.json()["notes"] == []
    assert len((await client.get("/api/tickets")).json()["items"]) == 1

    await client.post("/api/auth/logout", headers=csrf_headers(client))
    await login(client, "emp2@example.test")
    assert (await client.get(f"/api/tickets/{ticket['id']}")).status_code == 404

    await client.post("/api/auth/logout", headers=csrf_headers(client))
    await login(client, "emp1@example.test")
    timeline = (await client.get(f"/api/cases/{case['id']}/timeline")).json()["items"]
    event_types = [event["event_type"] for event in timeline]
    assert "ticket.drafted" in event_types
    assert "ticket.created" in event_types


async def test_ticket_acl_update_and_optimistic_lock(client: AsyncClient):
    created = await create_confirmed_ticket(client)
    ticket = created["ticket"]

    await client.post("/api/auth/logout", headers=csrf_headers(client))
    await login(client, "approver@example.test")
    assert (await client.get(f"/api/tickets/{ticket['id']}")).status_code == 200
    denied = await client.patch(
        f"/api/tickets/{ticket['id']}",
        json={"version": ticket["version"], "fields": {"priority": "P1"}},
        headers=csrf_headers(client),
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "FORBIDDEN"

    await client.post("/api/auth/logout", headers=csrf_headers(client))
    await login(client, "support1@example.test")
    updated = await client.patch(
        f"/api/tickets/{ticket['id']}",
        json={
            "version": ticket["version"],
            "fields": {
                "priority": "P1",
                "priority_reason": "多人受影响，核心业务受阻。",
            },
        },
        headers=csrf_headers(client),
    )
    assert updated.status_code == 200, updated.text
    updated_ticket = updated.json()
    assert updated_ticket["priority"] == "P1"
    assert updated_ticket["version"] == ticket["version"] + 1

    conflict = await client.patch(
        f"/api/tickets/{ticket['id']}",
        json={"version": ticket["version"], "fields": {"environment": "Windows 10"}},
        headers=csrf_headers(client),
    )
    assert conflict.status_code == 409
    error = conflict.json()["error"]
    assert error["code"] == "TYPE_CONFLICT"
    assert error["details"]["current_version"] == updated_ticket["version"]

    await client.post("/api/auth/logout", headers=csrf_headers(client))
    await login(client, "emp1@example.test")
    employee_denied = await client.patch(
        f"/api/tickets/{ticket['id']}",
        json={"version": updated_ticket["version"], "fields": {"priority": "P2"}},
        headers=csrf_headers(client),
    )
    assert employee_denied.status_code == 403


async def test_ticket_transition_state_machine(client: AsyncClient):
    created = await create_confirmed_ticket(client)
    ticket = created["ticket"]
    await login(client, "support1@example.test")

    illegal = await client.post(
        f"/api/tickets/{ticket['id']}/transition",
        json={"version": ticket["version"], "to_status": "RESOLVED"},
        headers=csrf_headers(client),
    )
    assert illegal.status_code == 409
    assert illegal.json()["error"]["code"] == "INVALID_STATE"
    assert "ASSIGNED" in illegal.json()["error"]["details"]["allowed"]

    assigned = await client.post(
        f"/api/tickets/{ticket['id']}/transition",
        json={
            "version": ticket["version"],
            "to_status": "ASSIGNED",
            "assignee_id": "user_support_1",
        },
        headers=csrf_headers(client),
    )
    assert assigned.status_code == 200, assigned.text
    ticket = assigned.json()
    assert ticket["status"] == "ASSIGNED"
    assert ticket["assignee_name"] == "王工"

    in_progress = await client.post(
        f"/api/tickets/{ticket['id']}/transition",
        json={"version": ticket["version"], "to_status": "IN_PROGRESS"},
        headers=csrf_headers(client),
    )
    assert in_progress.status_code == 200
    ticket = in_progress.json()

    resolved = await client.post(
        f"/api/tickets/{ticket['id']}/transition",
        json={
            "version": ticket["version"],
            "to_status": "RESOLVED",
            "note": "已重新安装驱动并打印测试页。",
        },
        headers=csrf_headers(client),
    )
    assert resolved.status_code == 200
    ticket = resolved.json()
    assert ticket["status"] == "RESOLVED"
    assert ticket["notes"][-1]["content"] == "已重新安装驱动并打印测试页。"

    closed = await client.post(
        f"/api/tickets/{ticket['id']}/transition",
        json={"version": ticket["version"], "to_status": "CLOSED"},
        headers=csrf_headers(client),
    )
    assert closed.status_code == 200
    ticket = closed.json()

    reopened = await client.post(
        f"/api/tickets/{ticket['id']}/transition",
        json={"version": ticket["version"], "to_status": "REOPENED"},
        headers=csrf_headers(client),
    )
    assert reopened.status_code == 200
    ticket = reopened.json()
    assert ticket["status"] == "REOPENED"

    assigned_again = await client.post(
        f"/api/tickets/{ticket['id']}/transition",
        json={
            "version": ticket["version"],
            "to_status": "ASSIGNED",
            "assignee_id": "user_support_1",
        },
        headers=csrf_headers(client),
    )
    assert assigned_again.status_code == 200
    ticket = assigned_again.json()
    assert ticket["status"] == "ASSIGNED"

    await client.post(
        f"/api/tickets/{ticket['id']}/notes",
        json={"content": "已与用户确认，等待再次验证。"},
        headers=csrf_headers(client),
    )
    detail = (await client.get(f"/api/tickets/{ticket['id']}")).json()
    assert len(detail["notes"]) == 2
    timeline = (await client.get(f"/api/cases/{ticket['case_id']}/timeline")).json()["items"]
    event_types = [event["event_type"] for event in timeline]
    assert event_types.count("ticket.transitioned") == 6
    assert "ticket.updated" in event_types


async def test_assignee_recommendation_prefers_lower_load(client: AsyncClient):
    for _ in range(2):
        created = await create_confirmed_ticket(client)
        ticket = created["ticket"]
        assigned = await client.post(
            f"/api/tickets/{ticket['id']}/transition",
            json={
                "version": ticket["version"],
                "to_status": "ASSIGNED",
                "assignee_id": "user_support_2",
            },
            headers=csrf_headers(client),
        )
        assert assigned.status_code == 200, assigned.text

    await client.post("/api/auth/logout", headers=csrf_headers(client))
    await login(client, "support1@example.test")
    assignees = (await client.get("/api/tickets/assignees")).json()["items"]
    counts = {item["id"]: item["open_ticket_count"] for item in assignees}
    assert counts["user_support_2"] == 2
    assert counts["user_support_1"] == 0

    await client.post("/api/auth/logout", headers=csrf_headers(client))
    await login(client, "emp1@example.test")
    case = await create_case(client, "打印机又坏了")
    events = await send_message(
        client, case["id"], "打印机坏了，Windows 11，报错 0x0000011b，帮我建单"
    )
    draft = event_data(events, "ticket_draft")
    assert draft is not None
    assert draft["suggested_assignee_id"] == "user_support_1"
    assert "负载最低" in draft["suggested_assignee_reason"]


async def test_confirm_draft_rejects_stale_version(client: AsyncClient):
    await login(client, "emp1@example.test")
    case = await create_case(client)
    events = await send_message(
        client,
        case["id"],
        "打印机报错 0x0000011b，Windows 11，帮我建个工单",
    )
    draft = event_data(events, "ticket_draft")
    assert draft is not None
    await client.post("/api/auth/logout", headers=csrf_headers(client))

    await login(client, "support1@example.test")
    payload = {
        "case_id": case["id"],
        "draft_version": draft["version"] + 1,
        "fields": fields_from_draft(draft),
    }
    stale = await client.post(
        "/api/tickets", json=payload, headers=csrf_headers(client)
    )
    assert stale.status_code == 409
    error = stale.json()["error"]
    assert error["code"] == "TYPE_CONFLICT"
    assert error["details"]["current_version"] == draft["version"]
    assert (await client.get(f"/api/cases/{case['id']}/ticket-draft")).json()["status"] == "DRAFT"

    payload["draft_version"] = draft["version"]
    confirmed = await client.post(
        "/api/tickets", json=payload, headers=csrf_headers(client)
    )
    assert confirmed.status_code == 201, confirmed.text


async def test_cancelled_ticket_is_terminal(client: AsyncClient):
    created = await create_confirmed_ticket(client)
    ticket = created["ticket"]
    cancelled = await client.post(
        f"/api/tickets/{ticket['id']}/transition",
        json={
            "version": ticket["version"],
            "to_status": "CANCELLED",
            "note": "用户取消，无需继续处理。",
        },
        headers=csrf_headers(client),
    )
    assert cancelled.status_code == 200, cancelled.text
    cancelled_ticket = cancelled.json()
    assert cancelled_ticket["status"] == "CANCELLED"
    assert cancelled_ticket["notes"][-1]["content"] == "用户取消，无需继续处理。"

    reopened = await client.post(
        f"/api/tickets/{ticket['id']}/transition",
        json={"version": cancelled_ticket["version"], "to_status": "REOPENED"},
        headers=csrf_headers(client),
    )
    assert reopened.status_code == 409
    error = reopened.json()["error"]
    assert error["code"] == "INVALID_STATE"
    assert error["details"]["allowed"] == []


async def test_ticket_notes_reject_read_only_roles(client: AsyncClient):
    created = await create_confirmed_ticket(client)
    ticket = created["ticket"]

    await client.post("/api/auth/logout", headers=csrf_headers(client))
    await login(client, "approver@example.test")
    approver_note = await client.post(
        f"/api/tickets/{ticket['id']}/notes",
        json={"content": "审批人不应写入内部备注。"},
        headers=csrf_headers(client),
    )
    assert approver_note.status_code == 403
    approver_detail = await client.get(f"/api/tickets/{ticket['id']}")
    assert approver_detail.status_code == 200
    assert approver_detail.json()["notes"] == []

    await client.post("/api/auth/logout", headers=csrf_headers(client))
    await login(client, "emp1@example.test")
    employee_note = await client.post(
        f"/api/tickets/{ticket['id']}/notes",
        json={"content": "员工不应写入内部备注。"},
        headers=csrf_headers(client),
    )
    assert employee_note.status_code == 403


async def test_ticket_list_filters_and_employee_scope(client: AsyncClient):
    first = await create_confirmed_ticket(client)
    first_ticket = first["ticket"]
    await client.patch(
        f"/api/tickets/{first_ticket['id']}",
        json={
            "version": first_ticket["version"],
            "fields": {
                "priority": "P1",
                "priority_reason": "多人受影响，打印机无法使用。",
            },
        },
        headers=csrf_headers(client),
    )
    second = await create_confirmed_ticket(client)

    by_priority = await client.get("/api/tickets?priority=P1")
    assert by_priority.status_code == 200
    assert [item["id"] for item in by_priority.json()["items"]] == [first_ticket["id"]]

    by_category = await client.get("/api/tickets?category=hardware")
    assert {item["id"] for item in by_category.json()["items"]} == {
        first_ticket["id"],
        second["ticket"]["id"],
    }

    by_query = await client.get("/api/tickets?q=打印机")
    assert {item["id"] for item in by_query.json()["items"]} == {
        first_ticket["id"],
        second["ticket"]["id"],
    }

    assigned = await client.post(
        f"/api/tickets/{first_ticket['id']}/transition",
        json={
            "version": first_ticket["version"] + 1,
            "to_status": "ASSIGNED",
            "assignee_id": "user_support_1",
        },
        headers=csrf_headers(client),
    )
    assert assigned.status_code == 200, assigned.text
    by_assignee = await client.get("/api/tickets?assignee_id=user_support_1")
    assert [item["id"] for item in by_assignee.json()["items"]] == [first_ticket["id"]]

    await client.post("/api/auth/logout", headers=csrf_headers(client))
    await login(client, "emp2@example.test")
    assert (await client.get("/api/tickets")).json()["items"] == []


def test_triage_classification_priority_and_fields():
    assert asks_for_ticket("帮我建个工单") is True
    assert asks_for_ticket("打印机坏了怎么办") is False

    multi_user = build_triage(["多人无法登录 VPN，整个部门都断网了"])
    assert multi_user.category == "network_vpn"
    assert multi_user.priority == "P1"
    assert multi_user.priority_reason

    security = build_triage(["同事收到钓鱼邮件，账号可能被盗"])
    assert security.category == "security_incident"
    assert security.priority == "P1"

    ambiguous_printer = build_triage(["打印机坏了，帮我建个工单"])
    assert ambiguous_printer.category == "hardware"
    assert ambiguous_printer.priority == "P2"
    assert "environment" in ambiguous_printer.missing_fields
    assert "error_message" in ambiguous_printer.missing_fields

    printer = build_triage(
        ["打印机报错 0x0000011b，Windows 11，帮我建个工单"]
    )
    assert printer.category == "hardware"
    assert printer.environment == "Windows 11"
    assert "0x0000011b" in (printer.error_message or "")

    software_request = build_triage(["申请安装 Visio，能否帮我开通"])
    assert software_request.category == "software"
    assert software_request.priority == "P4"

    email = build_triage(
        ["邮箱无法发送邮件，Windows 11，报错 550 5.7.1"]
    )
    assert email.category == "email_collaboration"
    assert email.priority == "P2"
    assert email.affected_system == "企业邮箱"
