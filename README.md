# SafeDesk

可审计、可评估、可人工接管的企业服务台 Agent 工作台。

当前进度：**M3 审批与受控执行已完成并通过本机验收**。在 M2 分诊与工单之上，已接入只读诊断、写动作提议、固定参数快照、人工审批、受控执行、结果复核、幂等控制与数据库检查点。评估控制台、运营看板和管理配置页等 M4 内容尚未接入。

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
            └─ 显式工作流状态机 + 数据库检查点（无需 LangGraph 运行时）
```

- 模块化单体，不拆微服务；业务数据库是唯一事实源。
- 登录会话使用 HttpOnly Cookie，写请求要求 `X-CSRF-Token`。
- 导航和操作入口由服务端返回的权限生成，服务端同时强制资源归属。
- Admin 可查看审批队列，但不自动拥有 `approval:decide` 权限。
- M1 检索采用 `pg_trgm` 词法匹配 + 本地哈希向量重排；向量存储接口已隔离，后续可替换为 pgvector。
- M2 工单草稿持久化为 `DRAFT`，但不出现在工单列表；确认时与 Case 双向关联在同一事务中完成。
- M3 只读工具由服务端自动执行并记录审计；写工具只能经 Action/Approval 状态机调用，不提供公开的 `/tools/execute`。
- Action、Approval 和 ToolExecution 在批准前固定参数哈希；每个 Action 最多一条执行记录，重复批准返回首次执行结果。
- 工作流使用显式状态机与数据库检查点；检查点缺失时可由 Action/Approval 业务状态重建待审批节点。
- 工具策略与 Kill Switch 已提供 Admin API；可视化管理界面保留到 M4。
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

## M2 已实现

- 分诊：固定 7 类分类法、P1–P4 优先级与必填理由，抽取环境、错误码、影响系统和缺失字段。
- 信息不足：先进入 `NEEDS_INPUT` 并只追问，不创建草稿；补齐信息后才生成结构化草稿。
- 工单草稿：展示分类、优先级、字段、证据与推荐处理人；草稿不出现在工单列表，确认后才转为 `OPEN`。
- 工单管理：列表筛选、详情、字段修改、乐观锁冲突、状态流转、处理备注、Case 与 Ticket 双向关联。
- 处理人推荐：优先匹配分类技能组，再按当前活跃工单负载排序，并返回可解释的推荐理由。
- 权限：Employee 仅能读取本人工单；Support/Admin 可管理；Approver 只读且不返回内部备注；越权统一返回 404。
- 评估集：`apps/api/app/eval_data/ticket_80.jsonl` 共 80 条，覆盖 7 类分类和 P1–P4；规则基线与数据集预期一致性为分类 80/80、优先级 80/80。该结果仅用于固定集覆盖验证，不代表开放场景泛化准确率。
- 前端：`/tickets`、`/tickets/[id]`、Case 工作台工单草稿卡与确认后关联入口。

### M2 演示路径

1. 使用员工账号在 `/chat` 输入“打印机坏了，帮我建个工单”，确认只追问操作系统和报错信息。
2. 补充“Windows 11，报错 0x0000011b”，确认生成 `hardware/P2` 草稿、推荐处理人和缺失字段提示。
3. 切换到王工，在 Case 工作台核对并修改草稿后确认建单；Case 变为“已转工单”，并可通过 `/tickets` 打开详情。
4. 在工单详情修改优先级、分派处理人、流转状态并添加内部备注；切换到审批人确认只读且看不到内部备注。

## M3 已实现

- 动作识别：员工发起“重置 VPN 证书”或“申请应用访问权限”时，先生成写动作建议；安装类请求不会被误判为权限授予。
- 只读诊断：写动作前自动调用对应只读工具，记录工具参数、结果摘要与证据，并写入 `tool.read_executed`。
- 审批材料：Action 固定工具、参数、参数哈希、证据、影响范围、验证方式、回滚方案和 15 分钟有效期；Approval 保存独立参数快照与版本。
- 审批队列：`/approvals` 支持状态/风险筛选、详情查看、二次确认批准、拒绝原因必填、执行结果和阻断原因展示。
- 受控执行：批准后经 Tool Gateway 执行 Mock 写工具，支持 `success`、`fail`、`timeout` 三种演练模式；执行成功后再调用只读工具复核。
- 权限边界：申请人不能审批自己的动作；Admin 只有审批查看权限，没有 `approval:decide`；审批范围同时校验工具与申请人部门。
- 状态恢复：Action/Approval 状态、参数哈希、Case 状态、工具启停和 Kill Switch 均在执行前复核；满足条件后从 `await_approval` 恢复。
- 幂等与阻断：同一 Action 只创建一条 ToolExecution；重复批准不重复调用工具；过期、Case 关闭、工具停用或 Kill Switch 开启均阻断执行。
- Case 工作台：动作卡展示风险、固定参数、证据、验证/回滚方案、审批状态和执行结果；SSE 新增 `action` 事件并关联 `/approvals`。
- Admin API：`GET/PATCH /api/admin/tools` 管理工具启停与 Mock 模式，`GET/PUT /api/admin/kill-switch` 管理全局写操作暂停。

### M3 演示路径

1. 使用员工账号在 `/chat` 输入“我的 VPN 证书过期了，帮我重置证书”，确认只读诊断后 Case 进入 `AWAITING_APPROVAL`，页面展示固定参数和审批号。
2. 切换到审批人陈审批，在 `/approvals` 打开待审批动作，核对影响对象、参数哈希、证据、验证与回滚方案后批准。
3. 回到 Case 工作台，确认 Action/Execution 为 `SUCCEEDED`、只读复核通过、Case 进入 `RESOLVED`，时间线包含提议、审批、执行和验证事件。
4. 重复批准同一审批，确认返回同一执行结果且不新增 ToolExecution；管理员可通过 Admin API 演练工具停用、执行失败和 Kill Switch 阻断。

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

以下为 2026-11-06 的本机 M3 验收结果。

- `npm run typecheck`：通过。
- `npm run build`：通过，App Router 页面与动态路由成功生成。
- `pytest`：46/46 通过（覆盖检索、ACL、SSE、工单、动作识别、审批权限、过期/自审批/范围阻断、参数哈希、工具启停、Kill Switch、幂等执行、检查点恢复与审计；测试使用 SQLite 内存库）。
- `ruff check app migrations tests`：通过（FastAPI 的 `Depends` 默认参数规则 B008 已按框架惯例忽略）。
- Docker Compose 运行态验收：db/api/web 均健康，Alembic 为 `0004_actions_approvals_workflow (head)`，5 份演示知识成功加载。
- M3 端到端：经 Next 同源代理完成员工提议、只读诊断、审批人批准、Mock 工具执行、只读复核、Case 解决与 `/approvals` / Case 页面 200 验证。
- M3 幂等：重复批准返回同一 Execution，`tool.executed` 审计仍只有一条。
- M3 审计：确认存在 `tool.read_executed`、`action.proposed`、`approval.requested`、`approval.approved`、`tool.executing`、`tool.executed`、`action.verified`、`case.resolved` 事件。
- API/Web 日志：M3 端到端期间无未处理异常。
- M1 端到端：经 Next 同源代理验证 SSE `step/citation/token/status/done` 流式事件、`[1]` 引用与原文定位、无依据/敏感请求拒答、知识上传后检索和停用、Employee 知识列表 403 与来源 ACL，以及刷新不重复发送。
- Docker Compose 构建：`docker compose up -d --build` 成功，API/Web 镜像与运行态无未处理异常。
- 审计不可变：对 `audit_events` 执行 UPDATE 被 PostgreSQL 触发器拒绝。
- 中文往返：Case 标题创建与读取无误。
- M2 端到端：经 Next 同源代理验证模糊请求追问、补齐后草稿、Support 确认建单、Case/Ticket 双向关联、列表筛选、字段修改、分派、Approver 只读与 Employee 本人范围。
- M2 审计：确认存在 `ticket.drafted`、`ticket.created`、`ticket.updated`、`ticket.transitioned` 事件。

## 文档

- 设计系统：`docs/design-system.md`
- 信息架构与流程：`docs/ia-and-flows.md`
- 数据模型与状态机：`docs/data-model-and-state-machines.md`
- API 与 SSE 契约：`docs/openapi-and-sse.md`
- Case 工作台稿：`docs/wireframes/case-workspace.md`
- 审批队列稿：`docs/wireframes/approval-queue.md`
- 静态视觉预览：`docs/design-preview/preview.png`
