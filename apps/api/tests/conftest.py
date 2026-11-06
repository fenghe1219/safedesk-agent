import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SEED_DEMO"] = "false"
os.environ["DEMO_MODE"] = "true"
os.environ["SESSION_COOKIE_SECURE"] = "false"

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.rbac import Role
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.seed import DEMO_DOCUMENTS
from app.services.knowledge_service import create_document

TEST_PASSWORD = "Demo123!"
TEST_PASSWORD_HASH = hash_password(TEST_PASSWORD)

TEST_USERS = [
    {
        "id": "user_emp_1",
        "name": "员工一",
        "email": "emp1@example.test",
        "role": Role.EMPLOYEE.value,
        "department": "产品部",
    },
    {
        "id": "user_emp_2",
        "name": "员工二",
        "email": "emp2@example.test",
        "role": Role.EMPLOYEE.value,
        "department": "设计部",
    },
    {
        "id": "user_eval",
        "name": "评估员",
        "email": "eval@example.test",
        "role": Role.EVALUATOR.value,
        "department": "质量与评估",
    },
    {
        "id": "user_approver",
        "name": "审批人",
        "email": "approver@example.test",
        "role": Role.APPROVER.value,
        "department": "IT 安全",
    },
    {
        "id": "user_support_1",
        "name": "王工",
        "email": "support1@example.test",
        "role": Role.SUPPORT.value,
        "department": "桌面支持",
    },
    {
        "id": "user_support_2",
        "name": "李工",
        "email": "support2@example.test",
        "role": Role.SUPPORT.value,
        "department": "桌面支持",
    },
    {
        "id": "user_admin",
        "name": "管理员",
        "email": "admin@example.test",
        "role": Role.ADMIN.value,
        "department": "IT 管理",
    },
]

TEST_DOCUMENTS = DEMO_DOCUMENTS[:2]

test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
async def prepared_database():
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with TestSession() as db:
        for item in TEST_USERS:
            db.add(
                User(
                    id=item["id"],
                    name=item["name"],
                    email=item["email"],
                    password_hash=TEST_PASSWORD_HASH,
                    role=item["role"],
                    department=item["department"],
                    is_active=True,
                )
            )
        await db.commit()
        for item in TEST_DOCUMENTS:
            await create_document(
                db,
                title=item["title"],
                version=item["version"],
                owner_id="user_admin",
                raw_content=item["content"],
                source_type="markdown",
                acl={"departments": []},
            )
        await db.commit()
    yield
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


async def login(client: AsyncClient, email: str, password: str = TEST_PASSWORD):
    return await client.post("/api/auth/login", json={"email": email, "password": password})


def csrf_headers(client: AsyncClient) -> dict[str, str]:
    token = client.cookies.get("sd_csrf")
    assert token
    return {"X-CSRF-Token": token}
