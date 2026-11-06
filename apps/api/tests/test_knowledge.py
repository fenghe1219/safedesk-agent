from httpx import AsyncClient

from tests.conftest import csrf_headers, login


async def test_knowledge_search_returns_ranked_chunks(client: AsyncClient):
    await login(client, "admin@example.test")
    response = await client.get("/api/knowledge/search", params={"q": "VPN 证书无效"})
    assert response.status_code == 200
    data = response.json()
    assert data["items"]
    assert data["items"][0]["title"] == "VPN 使用与排障指南"
    assert data["items"][0]["score"] >= 0.2
    assert data["items"][0]["quote"]


async def test_knowledge_search_requires_view_permission(client: AsyncClient):
    await login(client, "emp1@example.test")
    response = await client.get("/api/knowledge/search", params={"q": "VPN"})
    assert response.status_code == 403


async def test_admin_can_upload_and_disable_document(client: AsyncClient):
    await login(client, "admin@example.test")
    content = (
        "# 量子咖啡机维护\n\n## 清洁流程\n\n"
        "打开设备舱门，取出滤网并冲洗，然后重新安装滤网。\n"
    )
    upload = await client.post(
        "/api/knowledge/documents",
        files={"file": ("quantum-coffee.md", content.encode("utf-8"), "text/markdown")},
        data={"title": "量子咖啡机维护", "version": "v1", "departments": ""},
        headers=csrf_headers(client),
    )
    assert upload.status_code == 201
    document = upload.json()
    assert document["status"] == "READY"
    assert document["chunk_count"] >= 1

    search = await client.get("/api/knowledge/search", params={"q": "量子咖啡机滤网"})
    assert search.status_code == 200
    assert search.json()["items"]

    disabled = await client.patch(
        f"/api/knowledge/documents/{document['id']}",
        json={"status": "DISABLED"},
        headers=csrf_headers(client),
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "DISABLED"

    search_after = await client.get(
        "/api/knowledge/search", params={"q": "量子咖啡机滤网"}
    )
    assert search_after.status_code == 200
    assert search_after.json()["items"] == []


async def test_evaluator_can_view_but_not_upload(client: AsyncClient):
    await login(client, "eval@example.test")
    listing = await client.get("/api/knowledge/documents")
    assert listing.status_code == 200
    assert len(listing.json()["items"]) == 2

    upload = await client.post(
        "/api/knowledge/documents",
        files={"file": ("blocked.md", b"# blocked", "text/markdown")},
        headers=csrf_headers(client),
    )
    assert upload.status_code == 403
