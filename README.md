# SafeDesk

可审计、可评估、可人工接管的企业服务台 Agent 工作台。

当前进度：**M0 工程骨架已完成并通过验收**，包括登录与 RBAC、Case 基础链路、数据库迁移、审计事件、Docker Compose 和角色化前端外壳。知识检索、工单、审批执行、评估等业务模块将在 M1–M4 接入。

![M0 登录页](docs/design-preview/m0-login.png)

## 快速启动

前置条件：Docker Desktop（包含 Docker Compose）。

```powershell
Copy-Item .env.example .env
docker compose up --build
```

打开 <http://localhost:3000/login>。首次启动会自动执行 Alembic 迁移并写入演示账号。

### 演示账号

统一密码：`Demo123!`

| 角色 | 邮箱 | 姓名 | 部门 |
| --- | --- | --- | --- |
| 员工 | `lin.xiao@example.test` | 林晓 | 产品部 |
| 支持专员 | `wang.gong@example.test` | 王工 | 桌面支持 |
| 审批人 | `chen.shenpi@example.test` | 陈审批 | IT 安全 |
| 管理员 | `admin@example.test` | 管理员 | IT 管理 |
| 评估员 | `eval@example.test` | 评估员 | 质量与评估 |
| 审计员 | `audit@example.test` | 审计员 | 内审 |

登录后可通过顶部“演示身份”切换角色。演示模式只使用合成数据。

## 架构

```text
Browser
  └─ Next.js 15 / React 19 / TypeScript / Tailwind
       ├─ /api/* 同源代理（转发 Cookie、CSRF 与 Set-Cookie）
       └─ FastAPI / SQLAlchemy / Alembic
            ├─ PostgreSQL 16 + pgvector + pg_trgm
            └─ 后续：Python Worker + LangGraph 编排
```

- 模块化单体，不拆微服务；业务数据库是唯一事实源。
- 登录会话使用 HttpOnly Cookie，写请求要求 `X-CSRF-Token`。
- 导航和操作入口由服务端返回的权限生成，服务端同时强制资源归属。
- Admin 可查看审批队列，但不自动拥有 `approval:decide` 权限。
- 中文检索先采用 pgvector + pg_trgm，并保留分词适配边界。
- MVP 暂不引入 Redis。

## M0 已实现

- Docker Compose：PostgreSQL/pgvector、API、Web。
- 数据库：`users`、`user_sessions`、`cases`、`audit_events` 初始迁移；审计表 PostgreSQL 触发器禁止更新/删除。
- 认证：登录、退出、`/api/me`、演示身份切换。
- 权限：六类角色、服务端导航、Case 本人可见与跨角色只读规则。
- Case：创建、列表、详情、时间线，创建事件与业务写入同事务。
- 前端：登录页、角色化应用外壳、工作台、三栏 Case 骨架、各治理模块占位页、404/错误/加载态。
- 契约基础：统一错误结构、请求 ID、OpenAPI、CSRF 和 Cookie 安全属性。

## 本地开发

前端：

```powershell
Set-Location apps/web
npm install
npm run dev
```

后端需要 Python 3.12 与 PostgreSQL 16：

```powershell
Set-Location apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
$env:DATABASE_URL = "postgresql+psycopg://safedesk:safedesk@localhost:5432/safedesk"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

验证命令：

```powershell
Set-Location apps/web
npm run typecheck
npm run build

Set-Location ..\api
pytest
ruff check .
```

## 当前验证状态

以下为 2026-11-05 的本机验收结果。

- `npm run typecheck`：通过。
- `npm run build`：通过，13 个 App Router 路由成功生成。
- Next.js 运行时冒烟：`/login` 返回 200；后端不可用时同源代理返回 502。
- `pytest`：12/12 通过（测试使用 SQLite 内存库，`tests/` 已作为包导入）。
- `ruff check .`：通过（FastAPI 的 `Depends` 默认参数规则 B008 已按框架惯例忽略）。
- Docker Compose 运行态验收：db/api/web 均健康；登录、CSRF、Case 创建/详情/时间线、演示身份切换、退出会话失效均通过。
- 审计不可变：对 `audit_events` 执行 UPDATE 被 PostgreSQL 触发器拒绝。
- 中文往返：Case 标题创建与读取无误。

## 文档

- 设计系统：`docs/design-system.md`
- 信息架构与流程：`docs/ia-and-flows.md`
- 数据模型与状态机：`docs/data-model-and-state-machines.md`
- API 与 SSE 契约：`docs/openapi-and-sse.md`
- Case 工作台稿：`docs/wireframes/case-workspace.md`
- 审批队列稿：`docs/wireframes/approval-queue.md`
- 静态视觉预览：`docs/design-preview/preview.png`
