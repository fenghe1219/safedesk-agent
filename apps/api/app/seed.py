import asyncio
import logging

from sqlalchemy import select

from app.core.rbac import Role
from app.core.security import hash_password, new_id
from app.db.session import SessionLocal
from app.models.user import User

logger = logging.getLogger(__name__)

DEMO_PASSWORD = "Demo123!"

DEMO_USERS: list[dict[str, str]] = [
    {
        "email": "lin.xiao@example.test",
        "name": "林晓",
        "role": Role.EMPLOYEE.value,
        "department": "产品部",
    },
    {
        "email": "wang.gong@example.test",
        "name": "王工",
        "role": Role.SUPPORT.value,
        "department": "桌面支持",
    },
    {
        "email": "chen.shenpi@example.test",
        "name": "陈审批",
        "role": Role.APPROVER.value,
        "department": "IT 安全",
    },
    {
        "email": "admin@example.test",
        "name": "管理员",
        "role": Role.ADMIN.value,
        "department": "IT 管理",
    },
    {
        "email": "eval@example.test",
        "name": "评估员",
        "role": Role.EVALUATOR.value,
        "department": "质量与评估",
    },
    {
        "email": "audit@example.test",
        "name": "审计员",
        "role": Role.AUDITOR.value,
        "department": "内审",
    },
]


async def seed_demo_users() -> int:
    created = 0
    password_hash = hash_password(DEMO_PASSWORD)
    async with SessionLocal() as db:
        for item in DEMO_USERS:
            result = await db.execute(select(User).where(User.email == item["email"]))
            if result.scalar_one_or_none() is not None:
                continue
            db.add(
                User(
                    id=new_id("user"),
                    name=item["name"],
                    email=item["email"],
                    password_hash=password_hash,
                    role=item["role"],
                    department=item["department"],
                    is_active=True,
                )
            )
            created += 1
        await db.commit()
    if created:
        logger.info("Seeded %s demo users", created)
    return created


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_demo_users())
