# SafeDesk

可审计、可评估、可人工接管的企业服务台 Agent 工作台。

当前进度：**M1 知识闭环已完成并通过本机验收**。在 M0 骨架之上，已接入文档导入、切分与索引、带 ACL 的混合检索、流式回答、引用与原文定位、无依据拒答，以及可用的 Case 对话工作台。工单、审批执行、评估等模块将在 M2–M4 接入。

![M0 登录页](docs/design-preview/m0-login.png)

## 快速启动

前置条件：Docker Desktop（包含 Docker Compose）。

```powershell
Copy-Item .env.example .env
docker compose up --build
```

打开 <http://localhost:3000/login>。首次启动会自动执行 Alembic 迁移，并写入演示账号与合成知识文档。

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
- M1 检索采用 `pg_trgm` 词法匹配 + 本地哈希向量重排；向量存储接口已隔离，后续可替换为 pgvector。
- MVP 暂不引入 Redis。

## M0 已实现

- Docker Compose：PostgreSQL/pgvector、API、Web。
- 数据库：`users`、`user_sessions`、`cases`、`audit_events` 初始迁移；审计表 PostgreSQL 触发器禁止更新/删除。
- 认证：登录、退出、`/api/me`、演示身份切换。
- 权限：六类角色、服务端导航、Case 本人可见与跨角色只读规则。
- Case：创建、列表、详情、时间线，创建事件与业务写入同事务。
- 前端：登录页、角色化应用外壳、工作台、三栏 Case 骨架、各治理模块占位页、404/错误/加载态。
- 契约基础：统一错误结构、请求 ID、OpenAPI、CSRF 和 Cookie 安全属性。

## M1 已实现

- 知识库：Admin 可上传 Markdown/TXT/PDF，自动解析章节、页码、字符偏移并切分索引；Evaluator 只读查看。
- 检索：按文档状态与部门 ACL 过滤，使用中文词法匹配与本地哈希向量进行混合排序，并保留阈值拒答。
- 对话：Case 消息持久化，`POST /api/cases/{id}/messages` 返回 SSE 步骤、token、引用、状态和 done 事件。
- 回答：结构包含结论、处理步骤、下一步；回答只引用检索 chunk，服务端生成引用快照，不允许前端反推来源。
- 拒答：敏感越权、提示注入式请求与无足够证据的问题不生成操作步骤，记录 `answer.refused` 审计事件。
- 来源定位：引用可打开原文阅读器，按字符偏移高亮精确片段；文档停用后历史引用标记“来源已停用”。
- 工作台：新建 Case 后自动发起首轮问题，展示流式步骤、回答、证据面板、精确状态与时间线。
- 演示数据：空库启动即包含 VPN、打印机、账号锁定、敏感数据规范和会议室五份合成知识文档。

### M1 演示路径

1. 使用员工账号登录，在 `/chat` 输入“我的 VPN 一直连不上，提示证书无效”。
2. Case 自动检索并流式回答，中间栏展示结论、步骤和引用；点击“查看原文”核对高亮片段。
3. 新建 Case 输入“帮我查一下同事的工资”，确认安全拒答且没有引用或越权动作。
4. 切换到管理员，在 `/knowledge` 上传 Markdown、重建索引，并用“检索测试”检查命中片段。

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

以下为 2026-11-06 的本机验收结果。

- `npm run typecheck`：通过。
- `npm run build`：通过，13 个 App Router 路由成功生成。
- Next.js 运行时冒烟：`/login` 返回 200；后端不可用时同源代理返回 502。
- `pytest`：20/20 通过（覆盖检索、ACL、流式回答、引用定位、拒答与文档启停；测试使用 SQLite 内存库）。
- `ruff check .`：通过（FastAPI 的 `Depends` 默认参数规则 B008 已按框架惯例忽略）。
- Docker Compose 运行态验收：db/api/web 均健康，`0002` 迁移和 5 份演示知识成功加载；`/login` 返回 200，`/api/health` 数据库正常。
- M1 端到端：经 Next 同源代理验证 SSE `step/citation/token/status/done` 流式事件、`[1]` 引用与原文定位、无依据/敏感请求拒答、知识上传后检索和停用、Employee 知识列表 403 与来源 ACL，以及刷新不重复发送。
- Docker Compose 构建：`docker compose up --build` 成功，API/Web 镜像与运行态无未处理异常。
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
