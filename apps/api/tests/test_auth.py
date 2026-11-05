from httpx import AsyncClient

from tests.conftest import csrf_headers, login


async def test_health(client: AsyncClient):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


async def test_login_and_me(client: AsyncClient):
    response = await login(client, "emp1@example.test")
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["role"] == "employee"
    assert data["user"]["role_label"] == "员工"
    assert data["permissions"]["case:create"] is True
    assert data["demo_mode"] is True
    assert data["csrf_token"]
    assert client.cookies.get("sd_session")
    assert client.cookies.get("sd_csrf")

    me_response = await client.get("/api/me")
    assert me_response.status_code == 200
    assert me_response.json()["user"]["email"] == "emp1@example.test"


async def test_login_rejects_bad_password(client: AsyncClient):
    response = await login(client, "emp1@example.test", "wrong-password")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_me_requires_auth(client: AsyncClient):
    response = await client.get("/api/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_demo_switch_changes_role(client: AsyncClient):
    await login(client, "emp1@example.test")
    response = await client.post(
        "/api/demo/switch-user",
        json={"role": "approver"},
        headers=csrf_headers(client),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["role"] == "approver"
    assert data["permissions"]["approval:decide"] is True

    me_response = await client.get("/api/me")
    assert me_response.status_code == 200
    assert me_response.json()["user"]["role"] == "approver"


async def test_demo_switch_requires_csrf(client: AsyncClient):
    await login(client, "emp1@example.test")
    response = await client.post("/api/demo/switch-user", json={"role": "approver"})
    assert response.status_code == 403


async def test_logout_revokes_session(client: AsyncClient):
    await login(client, "emp1@example.test")
    response = await client.post("/api/auth/logout", headers=csrf_headers(client))
    assert response.status_code == 204
    me_response = await client.get("/api/me")
    assert me_response.status_code == 401
