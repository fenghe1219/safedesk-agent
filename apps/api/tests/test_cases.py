from httpx import AsyncClient

from tests.conftest import csrf_headers, login


async def create_case(client: AsyncClient, title: str = "VPN 无法连接"):
    return await client.post(
        "/api/cases",
        json={"title": title},
        headers=csrf_headers(client),
    )


async def test_case_create_requires_csrf(client: AsyncClient):
    await login(client, "emp1@example.test")
    response = await client.post("/api/cases", json={"title": "VPN 无法连接"})
    assert response.status_code == 403


async def test_case_create_and_read(client: AsyncClient):
    await login(client, "emp1@example.test")
    response = await create_case(client)
    assert response.status_code == 201
    case = response.json()
    assert case["status"] == "NEW"
    assert case["status_label"] == "新问题"
    assert case["phase"] == "intake"

    list_response = await client.get("/api/cases")
    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 1

    detail_response = await client.get(f"/api/cases/{case['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["title"] == "VPN 无法连接"

    timeline_response = await client.get(f"/api/cases/{case['id']}/timeline")
    assert timeline_response.status_code == 200
    assert timeline_response.json()["items"][0]["event_type"] == "case.created"


async def test_employee_cannot_read_other_case(client: AsyncClient):
    await login(client, "emp1@example.test")
    case = (await create_case(client)).json()

    await client.post("/api/auth/logout", headers=csrf_headers(client))
    await login(client, "emp2@example.test")
    response = await client.get(f"/api/cases/{case['id']}")
    assert response.status_code == 404


async def test_evaluator_cannot_create_case(client: AsyncClient):
    await login(client, "eval@example.test")
    response = await create_case(client)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_admin_can_read_all_cases(client: AsyncClient):
    await login(client, "emp1@example.test")
    case = (await create_case(client)).json()

    await login(client, "admin@example.test")
    response = await client.get(f"/api/cases/{case['id']}")
    assert response.status_code == 200
    assert response.json()["requester_id"] == "user_emp_1"
