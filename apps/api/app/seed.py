import asyncio
import logging

from sqlalchemy import select

from app.core.rbac import Role
from app.core.security import hash_password, new_id
from app.db.session import SessionLocal
from app.models.knowledge import KnowledgeDocument
from app.models.user import User
from app.services.knowledge_service import create_document

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

DEMO_DOCUMENTS: list[dict[str, str]] = [
    {
        "title": "VPN 使用与排障指南",
        "version": "v3",
        "content": """# VPN 使用与排障指南

本文适用于公司统一 VPN 客户端。以下步骤只处理客户端配置与证书问题，不包含网络设备变更。

## 连接前检查

1. 打开 VPN 客户端，确认服务器地址为公司内网地址。
2. 检查电脑时间是否自动同步；时间偏差会导致证书校验失败。
3. 确认当前网络可以访问公司登录页，再点击连接。

\f

## 证书失效

当证书过期时，客户端会提示“证书无效”“认证失败”或“需要重新登录”。只读检查显示证书已过期时，可以重置当前用户的 VPN 证书。

1. 打开 VPN 客户端，进入“证书管理”。
2. 点击“重置证书”，按提示重新登录公司账号。
3. 等待证书重新签发，通常需要 1 分钟。
4. 重新连接 VPN，确认状态显示为已连接。

## 重新连接

如果重置后仍然无法连接，先退出客户端并重启电脑，再次打开 VPN 客户端。仍然失败时，请记录完整报错、发生时间和当前网络，提交工单由桌面支持核对客户端日志。
""",
    },
    {
        "title": "打印机驱动与报错处理",
        "version": "v2",
        "content": """# 打印机驱动与报错处理

本文适用于 Windows 10/11 办公电脑。修改驱动前请确认当前用户有安装软件的权限。

## 报错 0x0000011b

报错 0x0000011b 通常由 Windows 打印共享安全更新与旧版驱动不兼容导致。

1. 打开“设置 > 蓝牙和其他设备 > 打印机和扫描仪”。
2. 删除当前打印机，并勾选删除驱动和队列。
3. 从软件中心安装最新版打印机驱动。
4. 重新添加网络打印机，使用公司打印服务器地址。
5. 打印测试页，确认队列中没有残留任务。

## 无法发送到打印机

如果打印任务一直显示“正在打印”，先检查打印机是否在线和纸张状态。确认在线后，打开打印队列取消全部任务，再重启打印服务或电脑。

仍然失败时，请补充操作系统版本、错误码和打印机型号，创建工单由桌面支持处理。
""",
    },
    {
        "title": "账号锁定与自助解锁",
        "version": "v1",
        "content": """# 账号锁定与自助解锁

## 自助解锁

公司账号连续输入错误密码后会临时锁定 15 分钟。可以等待锁定自动解除，也可以通过账号自助服务重置密码。

1. 打开账号自助服务，输入公司邮箱。
2. 完成多因素认证，选择“重置密码”。
3. 设置符合密码策略的新密码。
4. 返回登录页重新登录，并确认邮箱和协作工具可以正常使用。

## 需要人工处理

如果无法完成多因素认证，或账号仍提示已停用，请不要反复尝试密码。记录工号和报错时间，创建工单由 IT 服务台核验身份。
""",
    },
    {
        "title": "敏感数据与权限访问规范",
        "version": "v1",
        "content": """# 敏感数据与权限访问规范

## 基本原则

员工只能访问完成本职工作所必需的数据。薪资、绩效、身份证件、联系方式和账号凭据属于敏感信息，不得通过公开渠道查询或导出。

## 申请授权

确需访问其他部门数据时，应提交业务负责人审批的数据权限申请，说明用途、范围和保留期限。获批后由管理员按最小权限原则开通。

## 安全替代

无法直接访问时，可以联系对应业务负责人，或创建工单向有权限的人员说明需求。不要尝试绕过权限校验、共享账号或导出明文密码。
""",
    },
    {
        "title": "会议室与访客接待说明",
        "version": "v1",
        "content": """# 会议室与访客接待说明

## 预订会议室

1. 打开协作工具的“会议室”页面。
2. 选择日期、时间段和容纳人数，查看可用房间。
3. 填写会议主题并提交预订。
4. 如需会议设备，提前 30 分钟到现场测试投屏和视频会议。

## 访客接待

访客到达前，由接待人完成访客登记并确认访问区域。访客应在前台领取临时访客证，由员工全程陪同进入办公区。
""",
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


async def seed_demo_knowledge() -> int:
    created = 0
    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.role == Role.ADMIN.value).limit(1))
        owner = result.scalar_one_or_none()
        if owner is None:
            return 0
        for item in DEMO_DOCUMENTS:
            existing = await db.execute(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.title == item["title"],
                    KnowledgeDocument.version == item["version"],
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue
            await create_document(
                db,
                title=item["title"],
                version=item["version"],
                owner_id=owner.id,
                raw_content=item["content"],
                source_type="markdown",
                acl={"departments": []},
            )
            created += 1
        await db.commit()
    if created:
        logger.info("Seeded %s demo knowledge documents", created)
    return created


async def seed_demo_data() -> tuple[int, int]:
    users = await seed_demo_users()
    documents = await seed_demo_knowledge()
    return users, documents


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_demo_data())
