# SafeDesk API 与 SSE 契约 v0.1

> 状态：M0–M4 已实现（审批、受控执行、评估、审计、看板、反馈与管理配置）。Case 更新订阅 SSE 仍为后续设计。
> 目标：覆盖 MVP 页面和状态变化，不提前设计生产级集成  
> 关联文档：`docs/data-model-and-state-machines.md`、`docs/ia-and-flows.md`

## 1. 通用约定

### 1.1 基础

- Base path：`/api`
- 编码：UTF-8 JSON
- 时间：ISO 8601 带偏移，例如 `2026-11-03T10:24:00+08:00`；数据库存 UTC。
- ID：不透明字符串，前端不得解析含义。
- 命名：JSON 使用 `snake_case`，与 Python/Pydantic 保持一致。
- 版本：MVP 通过 URL 前缀 `/api`；后续破坏性变更使用 `/api/v1`。

### 1.2 认证与会话

- 使用 HttpOnly、Secure、SameSite=Lax 的会话 Cookie。
- Next.js 通过同源 `/api` 反向代理访问 FastAPI，避免跨域 Cookie 和 CSRF 复杂度。
- 所有状态变更请求需要 CSRF Token；登录后由 `/api/me` 返回，前端放入 `X-CSRF-Token`。
- 会话过期返回 `401 UNAUTHENTICATED`，前端跳转登录并保留返回地址。
- 演示身份切换只允许在 `DEMO_MODE=true` 时启用。

### 1.3 权限

- 所有端点默认需要认证，登录端点除外。
- 服务端按角色 + 资源归属 + 部门/审批范围校验，不信任客户端传入的 `user_id`。
- 列表接口返回当前用户可见范围，不返回“总数很大但都被过滤”的误导数据。
- 权限不足返回 `403 FORBIDDEN`，不泄露资源是否存在。
- 返回的 `permissions` 只用于 UI 呈现，不作为安全边界。

### 1.4 错误格式

```json
{
  "error": {
    "code": "APPROVAL_REQUIRED",
    "message": "该操作需要有效审批",
    "request_id": "req_01J...",
    "details": {}
  }
}
```

- `message` 面向用户，可安全展示；`details` 只放非敏感结构化信息。
- 不返回堆栈、SQL、密钥、系统 Prompt 或内部策略全文。
- 常见错误码：`UNAUTHENTICATED`、`FORBIDDEN`、`NOT_FOUND`、`INVALID_STATE`、`VALIDATION_ERROR`、`APPROVAL_REQUIRED`、`APPROVAL_EXPIRED`、`TYPE_CONFLICT`、`VERSION_CONFLICT`、`SELF_APPROVAL_FORBIDDEN`、`OUT_OF_SCOPE`、`CASE_CLOSED`、`TOOL_DISABLED`、`KILL_SWITCH_ENABLED`、`TOOL_FAILED`、`TOOL_TIMEOUT`、`VERIFICATION_FAILED`、`RATE_LIMITED`、`MODEL_UNAVAILABLE`、`RETRIEVAL_TIMEOUT`。

### 1.5 分页、筛选与并发

- 列表使用 cursor 分页：`?limit=20&cursor=...`，响应 `{ "items": [], "next_cursor": null }`。
- 筛选参数显式白名单；未知参数返回 `VALIDATION_ERROR`。
- 工单更新使用 `version` 乐观锁；不匹配返回 `409 TYPE_CONFLICT`。
- 创建类接口支持 `Idempotency-Key` 请求头；重复请求返回首次结果或 `409` 冲突，不重复创建。
- 所有响应带 `X-Request-ID`；SSE 连接的第一个事件也包含 `request_id`。

## 2. 端点目录

### 2.1 认证与当前用户

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/auth/login` | 公开 | 登录，设置会话 Cookie |
| POST | `/api/auth/logout` | 认证 | 退出并清除会话 |
| GET | `/api/me` | 认证 | 当前用户、角色、权限、导航 |
| POST | `/api/demo/switch-user` | 演示模式 | 切换演示身份，生产禁用 |

### 2.2 Case 与消息

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/cases` | 认证 | 我的/授权范围 Case 列表 |
| POST | `/api/cases` | Employee+ | 创建 Case |
| GET | `/api/cases/{id}` | 有权限 | Case 摘要与当前状态 |
| GET | `/api/cases/{id}/messages` | 有权限 | 分页加载历史消息 |
| POST | `/api/cases/{id}/messages` | 有权限 | 发送消息，返回 SSE |
| GET | `/api/cases/{id}/action` | 有权限 | 最新 Action、Approval、Execution 与阻断原因 |
| GET | `/api/cases/{id}/checkpoints` | 有权限 | 工作流检查点 |
| POST | `/api/cases/{id}/stop` | 有权限 | 停止当前生成 |
| POST | `/api/cases/{id}/retry` | 有权限 | 重试上一条失败/停止回答 |
| POST | `/api/cases/{id}/close` | 有权限 | 关闭 Case |
| POST | `/api/cases/{id}/reopen` | 有权限 | 重新打开 Case |
| GET | `/api/cases/{id}/timeline` | 有权限 | 安全投影后的时间线 |
| GET | `/api/cases/{id}/events` | 有权限 | 跨角色 Case 更新 SSE |
| POST | `/api/messages/{message_id}/feedback` | 有权限 | 回答反馈，幂等更新本人反馈 |

已实现 Case 列表、创建、详情、消息、时间线、Action、检查点与消息反馈；`stop/retry/close/reopen/events` 仍为后续设计。

### 2.3 知识库

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/knowledge/documents` | Admin/Evaluator 只读 | 文档列表 |
| POST | `/api/knowledge/documents` | Admin | 上传文档 |
| GET | `/api/knowledge/documents/{id}` | Admin/Evaluator 只读 | 元数据与切分预览 |
| PATCH | `/api/knowledge/documents/{id}` | Admin | 启停或修改元数据 |
| DELETE | `/api/knowledge/documents/{id}` | Admin | 删除文档并失效索引 |
| POST | `/api/knowledge/documents/{id}/reindex` | Admin | 重建索引 |
| GET | `/api/knowledge/documents/{id}/chunks` | Admin/Evaluator 只读 | 分页查看切分 |
| GET | `/api/knowledge/documents/{id}/file` | 有引用权限 | 返回原文件流 |
| GET | `/api/knowledge/documents/{id}/locator` | 有引用权限 | 根据 chunk 返回页码、章节、偏移和 bbox |
| GET | `/api/knowledge/search?q=` | Admin/Evaluator | 检索测试，返回排序后的 chunk 快照 |

### 2.4 工单

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/tickets` | 授权范围 | 工单列表，支持状态/分类/优先级/处理人/关键词筛选 |
| POST | `/api/tickets` | Support/Admin | 从草稿创建工单 |
| GET | `/api/tickets/{id}` | 有权限 | 工单详情 |
| PATCH | `/api/tickets/{id}` | Support/Admin | 修改字段，带 version |
| POST | `/api/tickets/{id}/transition` | Support/Admin | 状态流转 |
| POST | `/api/tickets/{id}/notes` | Support/Admin | 添加处理备注 |
| GET | `/api/tickets/assignees` | 有工单权限 | 可分派人员与活跃负载 |
| GET | `/api/cases/{id}/ticket-draft` | 有 Case 权限 | 读取 Case 的待确认草稿 |
| GET | `/api/tickets/{id}/export` | P1 | 导出 JSON |

工单 ACL：

- Employee 只能访问 `requester_id = current_user` 的工单；越权统一返回 `404 NOT_FOUND`，不泄露资源是否存在。
- Support/Admin 可管理工单；Approver 可只读，但详情不返回内部处理备注。
- `DRAFT` 草稿不出现在 `/api/tickets` 列表，只能通过 Case 的草稿端点读取；确认时校验 `draft_version`。

### 2.5 审批

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/approvals` | Approver/Admin（`approval:view`） | 审批队列，可按状态筛选 |
| GET | `/api/approvals/{approval_id}` | 审批范围 | 审批详情、证据、执行结果与阻断原因 |
| POST | `/api/approvals/{approval_id}/approve` | Approver（`approval:decide`） | 批准并恢复执行，幂等 |
| POST | `/api/approvals/{approval_id}/reject` | Approver（`approval:decide`） | 拒绝，原因必填 |

- 路径参数是 `approval_id`，不是 Action ID。
- 申请人不能审批自己的动作；Admin 默认只有查看权限，没有 `approval:decide`。
- 审批范围同时校验工具白名单和申请人部门。
- 不提供公开 `/tools/execute`；工具只能由工作流内部经 Tool Gateway 调用。

### 2.6 审计、评估、看板、配置

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/audit/events` | Auditor/Admin（`audit:view`） | 审计查询，支持过滤、分页与脱敏 payload |
| GET | `/api/eval/datasets` | Evaluator/Admin（`eval:manage`） | 数据集列表 |
| GET | `/api/eval/prompts` | Evaluator/Admin | 可用 Prompt 版本列表 |
| POST | `/api/eval/datasets/import` | Evaluator/Admin | 导入 JSONL/CSV，最多 500 条 |
| GET | `/api/eval/datasets/{dataset_id}` | Evaluator/Admin | 数据集与样本 |
| POST | `/api/eval/runs` | Evaluator/Admin | 启动并同步完成一次评估 |
| POST | `/api/eval/experiments` | Evaluator/Admin | 一次运行 2–4 个变体，自动与首个基线对比 |
| GET | `/api/eval/runs` | Evaluator/Admin | 运行列表，可按数据集过滤 |
| GET | `/api/eval/compare` | Evaluator/Admin | 对比两次 Run 的指标与回归门禁 |
| GET | `/api/eval/runs/{run_id}` | Evaluator/Admin | 运行详情、指标与样本结果 |
| GET | `/api/eval/runs/{run_id}/results` | Evaluator/Admin | 样本结果分页与人工复核筛选 |
| PATCH | `/api/eval/runs/{run_id}/results/{result_id}` | Evaluator/Admin | 人工 `PASS`/`FAIL` 与备注 |
| GET | `/api/dashboard?range=7d|30d` | Support/Approver/Admin/Auditor（`dashboard:view`） | 运营指标、样本量与口径 |
| GET | `/api/admin/settings` | Admin（`settings:manage`） | 配置汇总：运行参数、Prompt、分类与用户 |
| GET | `/api/admin/users` | Admin | 用户、角色、部门与启停状态 |
| PATCH | `/api/admin/users/{user_id}` | Admin | 调整角色/部门/启停，禁止自我降级和移除最后管理员 |
| GET | `/api/admin/runtime-config` | Admin | 读取运行时参数 |
| PUT | `/api/admin/runtime-config` | Admin | 更新运行时参数并写 `config.changed` |
| GET | `/api/admin/prompts` | Admin | Prompt 版本与激活状态 |
| POST | `/api/admin/prompts` | Admin | 新建 Prompt 版本 |
| POST | `/api/admin/prompts/{prompt_id}/activate` | Admin | 激活指定 Prompt 版本 |
| GET | `/api/admin/taxonomy` | Admin | 分类、优先级与角色权限矩阵 |
| GET | `/api/admin/tools` | Admin | 工具白名单与策略 |
| PATCH | `/api/admin/tools/{tool_name}` | Admin | 启停工具、设置 Mock 模式 |
| GET | `/api/admin/kill-switch` | Admin | 读取全局写操作暂停状态 |
| PUT | `/api/admin/kill-switch` | Admin | 开启/关闭 Kill Switch 并记录原因 |
| POST | `/api/admin/reset-demo` | Admin | 输入 `RESET-DEMO` 后重置演示数据并保留审计 |
| GET | `/api/memory?case_id=...` | 已登录用户（`case:read`） | 当前用户的 Case 记忆与用户偏好 |
| DELETE | `/api/memory/{entry_id}` | 已登录用户（`case:read`） | 删除自己的记忆条目；跨用户返回 404 |

上述端点均已实现。评估路径统一使用 `/api/eval/*`，不是 `/api/evaluations/*`；反馈路径是 `/api/messages/{message_id}/feedback`，不嵌套在 Case 路径下。

## 3. 关键请求与响应

### 3.1 当前用户 `GET /api/me`

```json
{
  "user": {
    "id": "user_1024",
    "name": "林晓",
    "email": "lin.xiao@example.test",
    "role": "employee",
    "role_label": "员工",
    "department": "产品部"
  },
  "permissions": {
    "case:create": true,
    "case:read": true,
    "case:read_all": false,
    "ticket:view": true,
    "ticket:manage": false,
    "approval:view": false,
    "approval:decide": false,
    "knowledge:view": false,
    "knowledge:manage": false,
    "eval:manage": false,
    "audit:view": false,
    "dashboard:view": false,
    "settings:manage": false
  },
  "navigation": [
    { "key": "chat", "label": "工作台", "href": "/chat", "icon": "workbench" },
    { "key": "tickets", "label": "我的工单", "href": "/tickets", "icon": "ticket" }
  ],
  "demo_mode": true,
  "csrf_token": "csrf_01J...",
  "default_path": "/chat"
}
```

### 3.2 Case 摘要 `GET /api/cases/{id}`

```json
{
  "id": "case_01J...",
  "title": "VPN 无法连接，需要重置证书",
  "status": "AWAITING_APPROVAL",
  "status_label": "等待审批",
  "phase": "approval",
  "requester_id": "user_1024",
  "current_node": "await_approval",
  "intent": "action_approval",
  "ticket_id": null,
  "action_id": "act_01J...",
  "created_at": "2026-11-03T09:30:00+08:00",
  "updated_at": "2026-11-03T09:35:10+08:00"
}
```

消息、时间线、动作和检查点分别通过独立端点加载，避免 Case 主接口返回过大的聚合对象。

### 3.2.1 关联动作 `GET /api/cases/{id}/action`

```json
{
  "id": "act_01J...",
  "case_id": "case_01J...",
  "tool_name": "reset_vpn_certificate",
  "tool_label": "重置 VPN 证书",
  "tool_type": "WRITE",
  "risk_level": "HIGH",
  "risk_label": "高风险",
  "status": "AWAITING_APPROVAL",
  "status_label": "等待审批",
  "args": {
    "user_id": "user_1024",
    "reason": "我的 VPN 证书过期了，帮我重置证书"
  },
  "args_hash": "sha256:...",
  "rationale": "只读检查显示 VPN 证书已过期，账号本身处于启用状态。",
  "impact": "仅影响当前用户 林晓（user_1024）；动作范围限定为「重置 VPN 证书」。",
  "verification_plan": "执行完成后调用只读工具复核证书状态，并记录验证结果。",
  "rollback_plan": "如执行结果异常，停止后续自动操作并转工单由桌面支持人工恢复。",
  "evidence_ids": ["chunk:...", "audit:..."],
  "requested_by_id": "user_1024",
  "requested_by_name": "林晓",
  "expires_at": "2026-11-03T09:50:10+08:00",
  "version": 1,
  "created_at": "2026-11-03T09:35:10+08:00",
  "updated_at": "2026-11-03T09:35:10+08:00",
  "case_status": "AWAITING_APPROVAL",
  "case_status_label": "等待审批",
  "approval": {
    "id": "apr_01J...",
    "action_id": "act_01J...",
    "status": "PENDING",
    "status_label": "待审批",
    "args_hash": "sha256:...",
    "approver_id": null,
    "approver_name": null,
    "decision_reason": null,
    "requested_at": "2026-11-03T09:35:10+08:00",
    "expires_at": "2026-11-03T09:50:10+08:00",
    "decided_at": null,
    "version": 1
  },
  "execution": null,
  "permissions": { "can_view": true, "can_decide": false },
  "blockers": []
}
```

- `blockers` 汇总权限、自审批、过期、Case 关闭、参数哈希、工具停用和 Kill Switch 等阻断原因。
- `execution` 在批准并开始执行后返回；同一 Action 最多一条执行记录。
- 没有 Action 的 Case 返回 `404 NOT_FOUND`。

### 3.2.2 检查点 `GET /api/cases/{id}/checkpoints`

```json
{
  "items": [
    {
      "id": "chk_01J...",
      "case_id": "case_01J...",
      "thread_id": "case_01J...",
      "sequence": 2,
      "node": "await_approval",
      "status": "waiting",
      "workflow_version": 1,
      "state": {
        "action_id": "act_01J...",
        "approval_id": "apr_01J...",
        "expires_at": "2026-11-03T09:50:10+08:00"
      },
      "created_at": "2026-11-03T09:35:10+08:00"
    }
  ]
}
```

检查点缺失但 Action 仍待审批时，读取动作会从业务状态重建 `await_approval` 检查点。

### 3.3 发送消息 `POST /api/cases/{id}/messages`

请求：

```json
{
  "content": "我的 VPN 一直连不上，提示证书无效。",
  "client_message_id": "web_01J..."
}
```

响应：`Content-Type: text/event-stream`，事件见第 4 节。该端点不接受 `role`、`user_id` 或工具名等客户端可控字段。

### 3.4 停止与重试

```json
POST /api/cases/{id}/stop
{
  "message_id": "msg_01J..."
}
```

- 仅停止当前流式回答，不取消已经提交的审批或执行。
- 停止后消息状态为 `STOPPED`，保留已生成内容。
- 重试创建新的助手消息，不复用旧消息 ID。

```json
POST /api/cases/{id}/retry
{
  "message_id": "msg_01J...",
  "client_message_id": "web_01J..."
}
```

### 3.5 创建工单 `POST /api/tickets`

```json
{
  "case_id": "case_01J...",
  "draft_version": 3,
  "fields": {
    "title": "VPN 证书过期",
    "description": "连接时提示证书无效，需重置证书",
    "category": "network_vpn",
    "priority": "P3",
    "priority_reason": "单人工作受阻，有临时替代方案",
    "affected_system": "企业 VPN",
    "environment": "Windows 11",
    "error_message": "证书无效",
    "urgency_reason": null,
    "suggested_assignee_id": "user_2001"
  }
}
```

- 服务端重新校验 Schema、分类枚举、优先级和权限。
- `draft_version` 防止覆盖他人刚修改的草稿。
- 创建成功后返回 Ticket 与更新后的 Case 状态。

### 3.6 审批决定

批准：

```json
POST /api/approvals/apr_01J.../approve
{
  "reason": "已核对用户身份和证书状态",
  "expected_args_hash": "sha256:...",
  "approval_version": 1
}
```

拒绝：

```json
POST /api/approvals/apr_01J.../reject
{
  "reason": "影响对象与工单不一致，请重新核对",
  "approval_version": 1
}
```

- 批准前服务端再次校验 `expected_args_hash`；不匹配返回 `409 TYPE_CONFLICT`。
- 审批人不能是申请人；不满足返回 `403 SELF_APPROVAL_FORBIDDEN`。
- 审批范围不匹配返回 `403 OUT_OF_SCOPE`；Case 已关闭返回 `409 CASE_CLOSED`。
- 重复批准已完成的审批返回首次 Execution，不重复调用工具；审批版本已变化返回 `409 VERSION_CONFLICT`。

### 3.7 工单更新与状态流转

```json
PATCH /api/tickets/tkt_01J...
{
  "version": 4,
  "fields": {
    "priority": "P2",
    "assignee_id": "user_2001"
  }
}
```

```json
POST /api/tickets/tkt_01J.../transition
{
  "version": 5,
  "to_status": "IN_PROGRESS",
  "note": "已联系用户，开始处理"
}
```

- 版本冲突返回当前版本和字段摘要，前端提示刷新。
- 非法流转返回 `INVALID_STATE`。

### 3.8 反馈

```json
POST /api/messages/msg_01J.../feedback
{
  "rating": "unhelpful",
  "reason": "missing_steps",
  "comment": "第三步没有说明证书在哪里下载"
}
```

- `rating`: `helpful | unhelpful`。
- 原因枚举：`inaccurate | no_citation | outdated | missing_steps | other`。
- 同一用户重复提交时更新原记录；反馈只形成候选样本，不直接修改知识库或模型。
- 提交成功写入 `feedback.submitted` 审计，payload 标记 `candidate_only=true`。

### 3.9 M4 评估、看板、审计与配置

启动评估：

```json
POST /api/eval/runs
{
  "dataset_id": "evalds_...",
  "label": "security baseline",
  "prompt_version": "m4-safe-v2-candidate",
  "model_settings": {"provider": "local-rules", "model": "extractive-rag-v1"},
  "retrieval_config": {"limit": 3, "min_score": 0.0},
  "run_config": {"mode": "single_config", "suite": "m4"}
}
```

- 响应包含 `status=COMPLETED`、`metrics`、`sample_count`、配置快照和 `finished_at`；当前评估同步执行，不创建后台任务。
- `metrics` 包含总体与分项样本量、延迟和成本估算；知识、分诊、安全分别返回对应指标。
- 对比：`GET /api/eval/compare?baseline_run_id=...&candidate_run_id=...`，响应包含逐指标 `delta`、`regressed`、`regression_blocked`、`threshold` 和 `blocking_metrics`。
- 看板：`GET /api/dashboard?range=7d` 或 `range=30d`，响应包含指标、`sample_sizes`、`methodology` 和评估趋势。
- 审计：`GET /api/audit/events?event_type=config.changed&q=...&offset=0&limit=50`；支持 `case_id`、`actor_id`、`result`、`start_at`、`end_at`。
- 运行参数：`PUT /api/admin/runtime-config`，字段包括 `retrieval_limit`、`max_context_chunks`、`retrieval_min_score`、`max_steps`、`approval_ttl_seconds`、`evaluation_regression_threshold`、`answer_style`、`answer_mode`、`memory_enabled`、`query_rewrite_enabled` 和 `agent_tools_enabled`。
- 用户、Prompt、工具、Kill Switch 和演示重置均走 `/api/admin/*`；所有写请求要求 CSRF，并写入 `config.changed` 或 `demo.reset` 审计。
- 未配置模型时 Prompt 只作为版本记录；配置 `LLM_PROVIDER=openai_compatible` 后，激活的 Prompt 会作为真实系统提示词。模型失败时回退本地规则。

### 3.10 Agent 记忆与消融

读取当前用户可见记忆：

```http
GET /api/memory?case_id=case_xxx
```

响应中的 `scope` 为 `CASE` 或 `USER`；`CASE` 条目绑定当前 Case，`USER` 条目是当前用户的显式偏好，默认 180 天过期。接口只返回当前用户自己的条目。

运行 RAG 消融：

```json
POST /api/eval/experiments
{
  "dataset_id": "evalds_xxx",
  "variants": [
    {
      "label": "完整 RAG 基线",
      "prompt_version": "m4-safe-v2-candidate",
      "model_settings": {"provider": "local-rules", "answer_mode": "local"},
      "retrieval_config": {"enabled": true, "limit": 3, "min_score": 0}
    },
    {
      "label": "关闭 RAG 消融",
      "prompt_version": "m4-safe-v2-candidate",
      "model_settings": {"provider": "local-rules", "answer_mode": "local"},
      "retrieval_config": {"enabled": false}
    }
  ]
}
```

响应包含 `runs`（每个变体）和 `comparisons`（首个基线对比其余变体）。知识指标新增 `retrieval_recall_at_k`、`retrieval_mrr`、`fallback_rate` 和 `avg_token_count`；逐样本 `actual` 保留 `rag_enabled`、`answer_mode`、`provider`、`model`、`fallback_reason`、`retrieved_titles` 和 `retrieval_rank`。

## 4. 消息流 SSE

`POST /api/cases/{id}/messages` 返回 `text/event-stream`，用于一次回答的流式过程。所有状态仍会落库；SSE 只是传输层。

### 4.1 事件格式

```text
id: 12
event: token
data: {"text":"根据内部文档，"}

```

每个事件包含单调递增的 `id`；`done` 或 `error` 是终止事件。连接中断后前端应重新拉取 Case，不要假设已收到全部 token。

### 4.2 事件类型

| 事件 | 数据 | 用途 |
| --- | --- | --- |
| `step` | `name`、`label`、`phase`、`status` | 显示当前步骤轨 |
| `token` | `text` | 流式追加回答文本 |
| `citation` | `index`、`chunk_id`、`doc_id`、`title`、`version`、`page`、`section`、`quote` | 生成引用面板 |
| `ticket_draft` | 完整 `TicketOut` 投影，另含 `ticket_id` | 显示或更新工单草稿卡 |
| `action` | `action`（完整 Action 投影）、`approval`（完整审批投影）、`case`（Case 摘要） | 一次更新动作卡、审批状态和 Case 状态 |
| `status` | `case_status`、`status_label`、`phase` | 更新 Case 状态 |
| `done` | `case_status`、`message_id`、`request_id`、`refused`、`evidence_count`；有动作时含 `action_id`，有草稿时含 `ticket_id` | 终止事件，保存消息并关联对象 |
| `error` | `code`、`message`、`retryable`、`request_id` | 终止事件，保留已有内容 |
| `heartbeat` | `ts` | 保持长连接，前端忽略内容 |

### 4.3 示例

```text
event: step
data: {"name":"retrieve","label":"正在检索知识库","phase":"retrieval","status":"running"}

event: step
data: {"name":"retrieve","label":"已找到 3 条相关依据","phase":"retrieval","status":"complete"}

event: token
data: {"text":"根据《VPN 使用与排障指南》，"}

event: citation
data: {"index":1,"chunk_id":"chunk_vpn_02","doc_id":"doc_vpn","title":"VPN 使用与排障指南","version":"v3","page":3,"section":"证书失效","quote":"当证书过期时，客户端会提示证书无效。"}

event: action
data: {"action":{"id":"act_01J...","case_id":"case_01J...","tool_name":"reset_vpn_certificate","tool_label":"重置 VPN 证书","tool_type":"WRITE","risk_level":"HIGH","risk_label":"高风险","status":"AWAITING_APPROVAL","status_label":"等待审批","args":{"user_id":"user_1024","reason":"我的 VPN 证书过期了，帮我重置证书"},"args_hash":"sha256:...","rationale":"只读检查显示 VPN 证书已过期，账号本身处于启用状态。","impact":"仅影响当前用户 林晓（user_1024）。","verification_plan":"执行完成后调用只读工具复核证书状态。","rollback_plan":"异常时转工单由桌面支持人工恢复。","evidence_ids":["chunk:...","audit:..."],"requested_by_id":"user_1024","requested_by_name":"林晓","expires_at":"2026-11-03T09:50:10+08:00","version":1,"created_at":"2026-11-03T09:35:10+08:00","updated_at":"2026-11-03T09:35:10+08:00"},"approval":{"id":"apr_01J...","action_id":"act_01J...","status":"PENDING","status_label":"待审批","args_hash":"sha256:...","approver_id":null,"approver_name":null,"decision_reason":null,"requested_at":"2026-11-03T09:35:10+08:00","expires_at":"2026-11-03T09:50:10+08:00","decided_at":null,"version":1},"case":{"id":"case_01J...","title":"VPN 无法连接，需要重置证书","status":"AWAITING_APPROVAL","status_label":"等待审批","phase":"approval","requester_id":"user_1024","current_node":"await_approval","intent":"action_approval","ticket_id":null,"action_id":"act_01J...","created_at":"2026-11-03T09:30:00+08:00","updated_at":"2026-11-03T09:35:10+08:00"}}

event: status
data: {"case_status":"AWAITING_APPROVAL","status_label":"等待审批","phase":"approval"}

event: done
data: {"case_status":"AWAITING_APPROVAL","message_id":"msg_01J...","request_id":"req_01J...","refused":false,"evidence_count":2,"action_id":"act_01J..."}
```

### 4.4 流式规则

- 不要发送模型的隐藏推理过程；`step` 只显示可理解的安全步骤。
- `token` 只追加文本，不携带 HTML；前端必须转义。
- 引用内容以服务端 `quote` 为准，前端不得用回答文本反推引用。
- `done` 之后不得再发送 `token`；`error` 之后也不得继续。
- 用户点击停止或断开连接时，服务端取消模型请求，保存 `STOPPED` 消息；已经产生的 token 不回滚。
- 模型不可用时发送 `error`，并保留已获得证据；不得自动执行任何写操作。
- 首 Token 目标 ≤ 2 秒；步骤事件可以在首 Token 前发送。

### 4.5 前端映射

| 事件 | UI 行为 |
| --- | --- |
| `step` | 更新顶部步骤文字和当前节点；完成时打勾 |
| `token` | 追加到当前回答卡，保持布局稳定 |
| `citation` | 追加到引用面板，按 `index` 排序 |
| `ticket_draft` | 在主卡区展示工单草稿，替换旧草稿摘要 |
| `action` | 用 `action` 更新动作卡、用 `approval` 更新审批状态、用 `case` 更新 Case 状态；有查看权限时链接到 `/approvals` |
| `status` | 更新 Case 状态标签和五阶段进度 |
| `done` | 结束加载态，开放反馈、停止/重试按钮状态 |
| `error` | 显示内联错误和重试；保留部分回答并标注未完成 |

### 4.6 M2 实际草稿载荷

`ticket_draft` 直接返回服务端投影后的草稿，前端不需要再用普通工单接口拼装：

```json
{
  "ticket_id": "tkt_01J...",
  "id": "tkt_01J...",
  "case_id": "case_01J...",
  "status": "DRAFT",
  "version": 2,
  "category": "hardware",
  "category_label": "硬件与设备",
  "priority": "P2",
  "priority_label": "P2 高",
  "priority_reason": "单人工作受阻，需要尽快恢复打印。",
  "title": "打印机报错 0x0000011b",
  "description": "Windows 11 打印机报错 0x0000011b，需要处理。",
  "environment": "Windows 11",
  "error_message": "0x0000011b",
  "missing_fields": [],
  "suggested_assignee_id": "user_2001",
  "suggested_assignee_name": "王工",
  "suggested_assignee_reason": "匹配桌面支持技能组，当前负载最低。",
  "fields": {}
}
```

确认建单后 `done` 事件同时返回 `ticket_id`，Case 端点随后返回 `status = TICKET_OPEN` 与同一个 `ticket_id`。

### 4.7 M3 动作载荷

`action` 事件不再返回扁平摘要，而是返回三个服务端投影：

- `action`: 工具、固定参数、参数哈希、证据、影响范围、验证/回滚方案、有效期和版本。
- `approval`: 审批 ID、状态、参数快照、审批人、决定原因和版本。
- `case`: 最新 Case 摘要，前端无需再猜测状态。

Case 工作台收到事件后直接替换动作卡；`done.action_id` 用于确认动作已持久化。后续聊天不会把仍在等待审批的 Case 覆盖成 `ANSWERED`。

## 5. Case 更新订阅 SSE（后续设计，未实现）

`GET /api/cases/{id}/events` 计划用于跨角色实时更新，例如审批人在另一个浏览器批准后，员工页面自动从“等待审批”切到“执行中”。M4 仍通过刷新和动作详情接口获取审批后状态。

### 5.1 事件类型

| 事件 | 数据 | 用途 |
| --- | --- | --- |
| `snapshot` | `case_status`、`status_label`、`phase`、`updated_at` | 连接建立后的当前状态 |
| `case_updated` | `case_id`、`status`、`status_label`、`phase`、`updated_at` | 刷新 Case 头部与主卡 |
| `action_updated` | `action_id`、`status`、`risk_level` | 更新动作卡 |
| `approval_updated` | `action_id`、`decision`、`decided_at` | 更新审批状态 |
| `ticket_updated` | `ticket_id`、`status`、`assignee_id` | 更新工单关联 |
| `timeline_appended` | `event_id`、`event_type`、`summary` | 追加时间线 |
| `heartbeat` | `ts` | 保持连接 |

### 5.2 重连

- 支持 `Last-Event-ID`，服务端从审计序列中补发遗漏事件。
- 若超过保留窗口或权限变化，发送 `snapshot` 并让前端重新拉取 Case。
- 连接建立后先发 `snapshot`，避免前端依赖本地猜测。
- 单个 Case 的订阅只允许有权限用户；连接时和每条事件前都可重新校验权限。

## 6. 错误与降级

| 场景 | 状态码 | 错误码 | UI |
| --- | --- | --- | --- |
| 未登录 | 401 | `UNAUTHENTICATED` | 跳转登录 |
| 无 Case 权限 | 403 | `FORBIDDEN` | 权限页，不泄露资源 |
| 审批过期 | 409 | `APPROVAL_EXPIRED` | 显示过期并给恢复路径 |
| 参数哈希不匹配 | 409 | `TYPE_CONFLICT` | 阻止执行，要求重新审批 |
| 工具禁用 | 409 | `TOOL_DISABLED` | 显示策略状态，不执行 |
| Kill Switch | 409 | `KILL_SWITCH_ENABLED` | 显示全局暂停原因 |
| Case 已关闭 | 409 | `CASE_CLOSED` | 阻止执行并要求重新发起 |
| 审批人越权 | 403 | `OUT_OF_SCOPE` | 不显示决定入口 |
| 申请人自审批 | 403 | `SELF_APPROVAL_FORBIDDEN` | 不显示决定入口 |
| 审批版本冲突 | 409 | `VERSION_CONFLICT` | 刷新审批详情后重试 |
| 模型不可用 | 503 | `MODEL_UNAVAILABLE` | 保留证据，允许检索/建单 |
| 检索超时 | 504 | `RETRIEVAL_TIMEOUT` | 可重试，不编造回答 |
| 请求过频 | 429 | `RATE_LIMITED` | 显示等待时间 |

## 7. 契约决策与遗留问题

| 问题 | 当前决策 |
| --- | --- |
| 是否对外提供工具执行接口 | 不提供；只允许工作流内部 Tool Gateway |
| Case 列表是否必须 | 必须；否则无法实现“最近会话”和我的 Case |
| Case 事件订阅是否 P0 | 后续增强；M4 未实现，当前通过刷新和详情接口获取状态 |
| 停止生成如何持久化 | 消息标记 `STOPPED`，保留部分内容，可重试 |
| 审批是否允许带参数修改 | P1；P0 只允许按原参数批准/拒绝 |
| 审计分页 | cursor；按时间和事件 ID 稳定排序 |
| SSE 是否发送模型内部推理 | 不发送；只发送安全步骤标签 |
| Prompt 文本是否驱动模型 | M4 尚未驱动；当前仅记录版本和激活状态 |

实现阶段应基于本文件生成实际 OpenAPI 文档，并用 FastAPI 类型和前端生成类型双向校验，避免文档与代码漂移。
