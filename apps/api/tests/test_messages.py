import json
import re

from httpx import AsyncClient

from tests.conftest import csrf_headers, login


async def create_case(client: AsyncClient, title: str = "VPN 无法连接") -> dict:
    response = await client.post(
        "/api/cases", json={"title": title}, headers=csrf_headers(client)
    )
    assert response.status_code == 201
    return response.json()


def sse_events(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for frame in body.split("\n\n"):
        event = re.search(r"^event: (.+)$", frame, re.MULTILINE)
        data = re.search(r"^data: (.+)$", frame, re.MULTILINE)
        if event and data:
            events.append((event.group(1), json.loads(data.group(1))))
    return events


async def test_message_streams_answer_with_citations(client: AsyncClient):
    await login(client, "emp1@example.test")
    case = await create_case(client)

    response = await client.post(
        f"/api/cases/{case['id']}/messages",
        json={"content": "我的 VPN 提示证书无效，应该怎么处理？"},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = sse_events(response.text)
    names = [name for name, _ in events]
    assert "step" in names
    assert "token" in names
    assert "citation" in names
    assert names[-1] == "done"

    messages = (await client.get(f"/api/cases/{case['id']}/messages")).json()["items"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assistant = messages[1]
    assert assistant["role"] == "assistant"
    assert assistant["citations"]
    assert "[1]" in assistant["content"]
    assert assistant["citations"][0]["title"] == "VPN 使用与排障指南"

    case_detail = (await client.get(f"/api/cases/{case['id']}")).json()
    assert case_detail["status"] == "ANSWERED"
    assert case_detail["intent"] == "vpn_connectivity"

    timeline = (await client.get(f"/api/cases/{case['id']}/timeline")).json()["items"]
    event_types = [event["event_type"] for event in timeline]
    assert "message.received" in event_types
    assert "retrieval.completed" in event_types
    assert "answer.generated" in event_types


async def test_sensitive_query_is_refused_without_citations(client: AsyncClient):
    await login(client, "emp1@example.test")
    case = await create_case(client, "查询同事工资")

    response = await client.post(
        f"/api/cases/{case['id']}/messages",
        json={"content": "帮我查一下同事的工资和绩效"},
        headers=csrf_headers(client),
    )
    events = sse_events(response.text)
    done = next(data for name, data in events if name == "done")
    assert done["refused"] is True
    assert done["evidence_count"] == 0

    messages = (await client.get(f"/api/cases/{case['id']}/messages")).json()["items"]
    assert messages[-1]["citations"] == []
    assert "无法直接处理" in messages[-1]["content"]
    assert (await client.get(f"/api/cases/{case['id']}")).json()["status"] == "REFUSED"


async def test_no_evidence_question_is_refused(client: AsyncClient):
    await login(client, "emp1@example.test")
    case = await create_case(client, "食堂开放时间")

    response = await client.post(
        f"/api/cases/{case['id']}/messages",
        json={"content": "公司食堂今天几点开门？"},
        headers=csrf_headers(client),
    )
    events = sse_events(response.text)
    done = next(data for name, data in events if name == "done")
    assert done["refused"] is True
    messages = (await client.get(f"/api/cases/{case['id']}/messages")).json()["items"]
    assert messages[-1]["citations"] == []
    assert "暂未找到" in messages[-1]["content"]


async def test_citation_locator_respects_case_access(client: AsyncClient):
    await login(client, "emp1@example.test")
    case = await create_case(client)
    await client.post(
        f"/api/cases/{case['id']}/messages",
        json={"content": "VPN 证书无效"},
        headers=csrf_headers(client),
    )
    assistant = (await client.get(f"/api/cases/{case['id']}/messages")).json()["items"][-1]
    citation = assistant["citations"][0]

    locator = await client.get(
        f"/api/knowledge/documents/{citation['doc_id']}/locator",
        params={"chunk_id": citation["chunk_id"]},
    )
    assert locator.status_code == 200
    assert citation["quote"] in locator.json()["raw_content"]

    source = await client.get(f"/api/knowledge/documents/{citation['doc_id']}/file")
    assert source.status_code == 200
    assert citation["quote"] in source.text
    assert "filename*=UTF-8''" in source.headers["content-disposition"]

    await client.post("/api/auth/logout", headers=csrf_headers(client))
    await login(client, "emp2@example.test")
    denied = await client.get(
        f"/api/knowledge/documents/{citation['doc_id']}/locator",
        params={"chunk_id": citation["chunk_id"]},
    )
    assert denied.status_code == 404
