# SafeDesk

可审计、可评估、可人工接管的企业服务台 Agent 工作台。

当前进度：**M4 评估、运营看板与管理配置已完成；M5 AI Agent 增强已实现并通过本机测试**。在 M4 之上新增 OpenAI-compatible Agent 决策循环、服务端工具策略、分层记忆、多轮查询改写、模型回退、Prompt 实际生效和 RAG 消融实验。默认仍可离线运行本地规则基线；只有配置模型后才会调用外部 Provider，Mock 写工具仍需人工审批。

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
- M4 工具策略、Kill Switch、运行参数、Prompt 版本、用户与部门均可在 `/settings` 管理；检索/上下文/审批 TTL/回归阈值等运行参数会实际影响服务端行为。
- M4 评估使用 40 条知识问答、80 条工单分诊和 15 条安全场景固定集；运行结果保留检索配置、指标、延迟、成本和人工复核记录。
- M5 Agent 采用严格 JSON 决策循环：模型可以提议只读工具，服务端负责白名单、启用状态、参数校验和 `user_id` 覆盖；写工具只生成 Action/Approval，审批前不会执行。
- M5 分层记忆按 `CASE` / `USER` 隔离：Case 记忆绑定 `case_id`，用户偏好绑定 `user_id` 并设置 180 天 TTL；读写删除均有审计。
- M5 多轮追问先做查询改写：模型可用时只输出改写问题，失败时回退本地规则；改写前后问题与记忆数量写入审计。
- M5 评估新增检索 Recall@K、MRR、回退率和平均 Token，并支持一次运行 2–4 个消融变体、自动与首个基线比较。
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
- 演示数据：空库启动即包含 12 篇合成知识文档，覆盖 VPN、打印、账号、邮箱、软件、硬件、安全事件和协作空间。

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

## M4 已实现

- 固定评估集：知识问答 40 条、工单分诊 80 条、安全场景 15 条；支持导入 JSONL/CSV，单次最多 500 条。
- 评估运行：同步执行知识、分诊、安全三类评估，保存 Prompt/模型/检索/Run 配置，以及逐样本实际输出、引用、延迟、Token、成本和失败原因。
- 人工复核：评估员可按样本标记 `PASS`/`FAIL` 并填写备注；复核结果与审计事件持久化。
- 回归门禁：`GET /api/eval/compare` 返回逐指标差异、动态阈值、阻断状态与阻断指标；阈值来自运行时配置。
- 运营看板：`/dashboard` 支持 `7d`/`30d`，展示 Case 总量、知识解决率、转单率、审批与失败、分类/优先级分布、人工修正率、处理与审批时长、重复执行阻断、回答/检索/工具延迟、成本和评估趋势，并返回各项样本量与口径说明。
- 审计检索：`/audit` 支持 Case、操作者、事件类型、结果、关键词、时间范围与分页过滤；敏感 payload 由服务端脱敏后展示。
- 消息反馈：`POST /api/messages/{message_id}/feedback` 支持 `helpful`/`unhelpful`、原因和备注；同一用户对同一消息幂等更新，反馈只作为候选样本，不直接修改知识库。
- 系统配置：`/settings` 管理工具启停与 Mock 模式、Kill Switch、运行参数、Prompt 版本、用户角色/部门/启停、分类矩阵与演示数据重置。
- 演示重置：管理员输入 `RESET-DEMO` 后清理业务数据并恢复 12 篇文档、3 个固定数据集和默认 Mock 工具配置；审计历史保留，重置动作写入 `demo.reset`。
- 数据库迁移：`0005_eval_dashboard_settings` 新增 `prompt_versions`、`eval_datasets`、`eval_items`、`eval_runs`、`eval_results`、`message_feedback`。

### M4 演示路径

1. 使用评估员登录 `/evaluations`，依次运行知识、分诊和安全三个固定数据集，查看样本量、指标、延迟、成本和逐样本结果。
2. 打开评估结果对比，确认指标差异、回归阈值和阻断标记；人工复核至少一条样本并填写备注。
3. 切换到审计员，在 `/dashboard` 查看 7d/30d 指标与样本量，在 `/audit` 按事件类型、关键词和时间范围检索并展开脱敏 payload。
4. 切换到管理员，在 `/settings` 调整检索 Top-K、上下文片段、审批 TTL 或回归阈值，保存后回到会话或评估确认生效；可查看 `config.changed` 审计。
5. 员工可在 Case 工作台对助手回答提交反馈，确认反馈只产生候选样本和 `feedback.submitted` 审计，不修改知识文档。

### M4 指标口径

- 评估基线为本地 `extractive-rag-v1` 规则实现；知识问答、分诊和安全指标仅用于固定集回归，不代表开放域准确率。
- 延迟、Token 和成本是本地估算，不构成外部模型账单或真实生产 SLA。
- 未配置模型时，回答生成仍由本地规则链路完成；配置 `LLM_PROVIDER=openai_compatible` 后，当前激活的 Prompt 会作为真实模型系统提示词。模型失败或输出非法时自动回退本地规则。
- 演示库包含 12 篇种子文档；若沿用旧演示卷，可能额外保留此前上传的历史文档，不影响种子数据完整性。

## M5 AI Agent 增强

- Provider：支持 OpenAI、Qwen、DeepSeek、Ollama 等 OpenAI-compatible `/chat/completions`；记录模型、Token、延迟和成本，优先使用 Provider usage，缺失时明确标记为估算。
- 决策循环：模型输出严格 JSON；最多调用次数由 `AGENT_MAX_MODEL_CALLS` 与运行时 `max_steps` 共同限制，避免无限循环。
- 工具边界：只读工具由服务端执行并把 observation 回传模型；写工具只生成 `write_proposal`，继续走既有 Action → Approval → ToolExecution 链路。
- 身份边界：模型提供的 `user_id` 会被服务端覆盖为 Case 请求人，禁止扩大影响范围；未知工具、停用工具、越权写操作记录 `agent.tool_rejected`。
- 引用边界：模型只选择 chunk 序号，引用标题、版本、页码、章节和原文快照由服务端从数据库重建；无合法引用时回退本地规则。
- 失败回退：超时、HTTP 错误、空响应、非法 JSON、引用越界和步数超限都会记录原因并回退，不影响 Case 继续处理。
- 分层记忆：`GET /api/memory?case_id=...` 查看当前用户可见记忆，`DELETE /api/memory/{entry_id}` 删除；跨用户删除返回 404。
- 消融实验：`POST /api/eval/experiments` 一次运行 2–4 个变体，自动对比首个基线；前端 `/evaluations` 提供“完整 RAG / 关闭 RAG”入口。
- 可观测性：新增 `agent.model_call`、`agent.tool_rejected`、`agent.output_rejected`、`agent.completed`、`agent.fallback`、`memory.written`、`memory.deleted`、`query.rewritten` 审计事件。

### 配置真实模型

在 `.env` 中设置（示例为本地 Ollama；云端 Provider 使用对应 Base URL 和 API Key）：

```dotenv
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_MODEL=qwen2.5:7b
LLM_API_KEY=
LLM_TIMEOUT_SECONDS=30
LLM_TEMPERATURE=0.1
LLM_MAX_OUTPUT_TOKENS=1200
AGENT_MAX_MODEL_CALLS=2
```

保持 `LLM_PROVIDER=disabled` 即可完全离线运行。不要在未实际运行模型的情况下，把本地估算指标写成真实模型效果。

### M5 演示路径

1. 使用员工账号在 `/chat` 输入“我的 VPN 证书无效，帮我看看状态”，观察只读工具诊断和带引用回答；消息下方显示模型与 Prompt 版本。
2. 输入“还是不行”，确认 Case 主题、环境和错误码被用于查询改写，并在时间线看到 `query.rewritten`。
3. 输入“以后回答请详细一些”，通过 `GET /api/memory?case_id=...` 确认用户偏好作用域为 `USER`；切换其他员工确认不可见。
4. 输入“帮我重置证书”，确认只生成待审批动作；切换到审批人前，数据库中没有对应 `ToolExecution`。
5. 使用评估员进入 `/evaluations`，选择知识问答集，运行“完整 RAG / 关闭 RAG”消融，查看 Recall@K 差异和回归阻断。

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

以下包含 2026-11-06 的 M4 验收结果和 2026-11-07 的 M5 扩展验证结果。

- `npm run typecheck`：通过。
- `npm run build`：通过，App Router 页面与动态路由成功生成。
- `pytest`：61/61 通过（M4 的 54 条基础上增加 Agent 只读工具 observation、写提议审批边界、未知工具拒绝、Provider 失败回退、记忆隔离/删除、查询改写和 RAG 消融实验；测试使用 SQLite 内存库）。
- `ruff check app migrations tests`：通过（FastAPI 的 `Depends` 默认参数规则 B008 已按框架惯例忽略）。
- Docker Compose 运行态验收：db/api/web 均健康，Alembic 为 `0005_eval_dashboard_settings (head)`，12/12 篇演示知识、40/80/15 三个固定数据集成功加载。
- M4 页面验收：Admin 的 `/evaluations`、`/dashboard`、`/audit`、`/settings` 均返回 200；Evaluator 仅可进入评估与知识，Auditor 仅可进入审计与看板，Support 可看板但不可审计，Employee 无看板/评估/审计/配置权限。
- M4 数据验收：看板接口同时支持 `range=7d` 与 `range=30d`；审计返回事件类型与脱敏 payload；配置接口返回运行时参数、Prompt、用户和分类矩阵。
- M4 真实评估：在 Compose/PostgreSQL 上运行安全场景固定集 15 条，Run 完成、结果分页 15 条、看板评估趋势和 `eval.run_completed` 审计均验证通过。
- M5 迁移与运行态：Compose 重建后 db/api/web 均健康，Alembic 为 `0006_agent_memory (head)`；管理员配置接口返回 `agent_runtime`，默认 `provider=disabled`、`configured=false`。
- M5 真实消融：在 Compose/PostgreSQL 上运行知识集 40 条（Recall 样本 34）。完整 RAG 的 Recall@K 为 97.06%、答案正确率 92.5%；关闭 RAG 后分别为 0.0% 和 15.0%，回归门禁阻断 `retrieval_recall_at_k`、`citation_consistency`、`refusal_accuracy`、`answer_accuracy`。
- M4 运行参数：检索 Top-K、最低相关度、上下文片段、回答风格、审批 TTL 和回归阈值均由服务端读取；测试验证了参数变化对检索、回答、审批和比较结果的实际影响。
- M4 存储修复：PostgreSQL 严格长度校验发现并修复了超长 M4 主键前缀；新增回归断言确保评估样本与反馈 ID 不超过 40 字符。
- M4 API/Web 日志：页面与真实评估验收期间无未处理异常。
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
- Agent 架构与信任边界：`docs/agent-architecture.md`
- 实验设计与指标口径：`docs/experiments.md`
- Case 工作台稿：`docs/wireframes/case-workspace.md`
- 审批队列稿：`docs/wireframes/approval-queue.md`
- 静态视觉预览：`docs/design-preview/preview.png`
