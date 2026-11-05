# SafeDesk API 与 SSE 契约 v0.1

> 状态：设计底稿，待进入实现前评审  
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
- 常见错误码：`UNAUTHENTICATED`、`FORBIDDEN`、`NOT_FOUND`、`INVALID_STATE`、`VALIDATION_ERROR`、`APPROVAL_REQUIRED`、`APPROVAL_EXPIRED`、`APPROVAL_CONFLICT`、`TYPE_CONFLICT`、`TOOL_DISABLED`、`KILL_SWITCH_ON`、`RATE_LIMITED`、`MODEL_UNAVAILABLE`、`RETRIEVAL_TIMEOUT`。

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
| GET | `/api/cases/{id}` | 有权限 | Case 工作台聚合数据 |
| GET | `/api/cases/{id}/messages` | 有权限 | 分页加载历史消息 |
| POST | `/api/cases/{id}/messages` | 有权限 | 发送消息，返回 SSE |
| POST | `/api/cases/{id}/stop` | 有权限 | 停止当前生成 |
| POST | `/api/cases/{id}/retry` | 有权限 | 重试上一条失败/停止回答 |
| POST | `/api/cases/{id}/close` | 有权限 | 关闭 Case |
| POST | `/api/cases/{id}/reopen` | 有权限 | 重新打开 Case |
| GET | `/api/cases/{id}/timeline` | 有权限 | 安全投影后的时间线 |
| GET | `/api/cases/{id}/events` | 有权限 | 跨角色 Case 更新 SSE |
| POST | `/api/cases/{id}/messages/{message_id}/feedback` | 有权限 | 回答反馈 |

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

### 2.4 工单

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/tickets` | 授权范围 | 工单列表 |
| POST | `/api/tickets` | Support/Admin | 从草稿创建工单 |
| GET | `/api/tickets/{id}` | 有权限 | 工单详情 |
| PATCH | `/api/tickets/{id}` | Support/Admin | 修改字段，带 version |
| POST | `/api/tickets/{id}/transition` | Support/Admin | 状态流转 |
| POST | `/api/tickets/{id}/notes` | Support/Admin | 添加处理备注 |
| GET | `/api/tickets/{id}/export` | P1 | 导出 JSON |

### 2.5 审批

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/approvals` | Approver/Admin 只读 | 审批队列 |
| GET | `/api/approvals/{id}` | 审批范围 | 审批详情与材料 |
| POST | `/api/approvals/{action_id}/approve` | Approver | 批准，幂等 |
| POST | `/api/approvals/{action_id}/reject` | Approver | 拒绝，原因必填 |

不提供公开 `/tools/execute`；工具只能由工作流内部经 Tool Gateway 调用。

### 2.6 审计、评估、看板、配置

| 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/audit` | Auditor/Admin/有限范围 | 审计查询 |
| GET | `/api/audit/{id}` | Auditor/Admin | 单条审计详情 |
| GET | `/api/evaluations/datasets` | Evaluator/Admin | 数据集列表 |
| POST | `/api/evaluations/datasets/import` | Evaluator/Admin | 导入 JSONL/CSV |
| GET | `/api/evaluations/datasets/{id}` | Evaluator/Admin | 数据集与样本 |
| POST | `/api/evaluations/runs` | Evaluator/Admin | 启动评估 |
| GET | `/api/evaluations/runs` | Evaluator/Admin | 运行列表 |
| GET | `/api/evaluations/runs/{id}` | Evaluator/Admin | 运行详情与指标 |
| GET | `/api/evaluations/runs/{id}/results` | Evaluator/Admin | 样本结果分页 |
| POST | `/api/evaluations/results/{id}/review` | Evaluator/Admin | 人工通过/失败与备注 |
| GET | `/api/dashboard/summary` | 授权角色 | 看板指标，`range=7d / 30d` |
| GET | `/api/admin/users` | Admin | 用户与角色 |
| PATCH | `/api/admin/users/{id}` | Admin | 调整角色/部门 |
| GET | `/api/admin/tools` | Admin | 工具白名单与策略 |
| PATCH | `/api/admin/tools/{name}` | Admin | 启停、风险、审批范围 |
| GET | `/api/admin/prompts` | Admin | Prompt 版本 |
| POST | `/api/admin/prompts` | Admin | 新建版本 |
| GET | `/api/admin/settings` | Admin | 当前系统配置 |
| PATCH | `/api/admin/settings/{key}` | Admin | 配置变更 |
| POST | `/api/admin/reset-demo` | Admin | 一键重置演示数据 |

## 3. 关键请求与响应

### 3.1 当前用户 `GET /api/me`

```json
{
  "user": {
    "id": "user_1024",
    "name": "林晓",
    "email": "lin.xiao@example.test",
    "role": "Employee",
    "department": "产品部"
  },
  "permissions": {
    "can_create_case": true,
    "can_view_tickets": true,
    "can_approve": false,
    "can_manage_knowledge": false
  },
  "navigation": [
    { "key": "chat", "label": "新建问题", "href": "/chat" },
    { "key": "cases", "label": "我的 Case", "href": "/chat" }
  ],
  "demo_mode": true,
  "csrf_token": "csrf_01J..."
}
```

### 3.2 Case 工作台 `GET /api/cases/{id}`

```json
{
  "case": {
    "id": "case_01J...",
    "title": "VPN 无法连接，需要重置证书",
    "status": "AWAITING_APPROVAL",
    "status_label": "等待审批",
    "phase": "approval",
    "requester": { "id": "user_1024", "name": "林晓" },
    "assignee": null,
    "current_node": "await_approval",
    "created_at": "2026-11-03T09:30:00+08:00",
    "updated_at": "2026-11-03T09:35:10+08:00"
  },
  "messages": [],
  "active_card": { "type": "action", "id": "act_01J..." },
  "evidence": [],
  "ticket": null,
  "action": {
    "id": "act_01J...",
    "tool_name": "reset_vpn_certificate",
    "tool_label": "重置 VPN 证书",
    "risk_level": "HIGH",
    "status": "AWAITING_APPROVAL",
    "rationale": "只读检查显示 VPN 证书已过期。",
    "impact": "仅影响当前用户 user_1024",
    "expires_at": "2026-11-03T09:45:00+08:00",
    "args": {
      "user_id": "user_1024",
      "reason": "证书已过期，只读检查确认"
    },
    "args_hash": "sha256:..."
  },
  "approval": {
    "id": "apr_01J...",
    "status": "PENDING",
    "requested_at": "2026-11-03T09:35:10+08:00"
  },
  "timeline": [],
  "permissions": {
    "can_approve": false,
    "can_reject": false,
    "can_create_ticket": false,
    "can_retry": false
  }
}
```

说明：

- `messages`、`evidence`、`timeline` 在生产中可单独分页；首屏返回最近一页。
- `active_card` 只指向一个主卡，避免前端猜当前该突出什么。
- `action.args` 对非审批人可只返回人类可读摘要；完整参数需要审批范围权限。
- 员工与审批人请求同一路径时，服务端裁剪字段，不返回无权查看的内部审计内容。

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
POST /api/approvals/act_01J.../approve
{
  "reason": "已核对用户身份和证书状态",
  "expected_args_hash": "sha256:...",
  "approval_version": 1
}
```

拒绝：

```json
POST /api/approvals/act_01J.../reject
{
  "reason": "影响对象与工单不一致，请重新核对",
  "approval_version": 1
}
```

- 批准前服务端再次校验 `expected_args_hash`；不匹配返回 `409 TYPE_CONFLICT`。
- 审批人不能是申请人；不满足返回 `403 FORBIDDEN`。
- 重复提交返回首次结果或 `APPROVAL_CONFLICT`，不重复执行。

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
POST /api/cases/case_01J.../messages/msg_01J.../feedback
{
  "rating": "not_helpful",
  "reason": "missing_steps",
  "comment": "第三步没有说明证书在哪里下载"
}
```

- `rating`: `helpful | not_helpful`。
- 原因枚举：`inaccurate | no_citation | outdated | missing_steps | other`。
- 反馈只形成候选样本（P1），不直接修改知识库或模型。

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
| `ticket_draft` | `ticket_id`、`status`、`missing_fields` | 显示或更新工单草稿卡 |
| `action` | `action_id`、`status`、`tool_name`、`tool_label`、`risk_level`、`expires_at` | 显示动作卡 |
| `status` | `case_status`、`status_label`、`phase` | 更新 Case 状态 |
| `done` | `case_status`、`message_id`、`request_id` | 终止事件，保存消息 |
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
data: {"action_id":"act_01J...","status":"AWAITING_APPROVAL","tool_name":"reset_vpn_certificate","tool_label":"重置 VPN 证书","risk_level":"HIGH","expires_at":"2026-11-03T09:45:00+08:00"}

event: status
data: {"case_status":"AWAITING_APPROVAL","status_label":"等待审批","phase":"approval"}

event: done
data: {"case_status":"AWAITING_APPROVAL","message_id":"msg_01J...","request_id":"req_01J..."}
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
| `action` | 在主卡区展示动作卡；若等待审批，显示有效期 |
| `status` | 更新 Case 状态标签和五阶段进度 |
| `done` | 结束加载态，开放反馈、停止/重试按钮状态 |
| `error` | 显示内联错误和重试；保留部分回答并标注未完成 |

## 5. Case 更新订阅 SSE

`GET /api/cases/{id}/events` 用于跨角色实时更新，例如审批人在另一个浏览器批准后，员工页面自动从“等待审批”切到“执行中”。

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
| Kill Switch | 409 | `KILL_SWITCH_ON` | 显示全局暂停原因 |
| 模型不可用 | 503 | `MODEL_UNAVAILABLE` | 保留证据，允许检索/建单 |
| 检索超时 | 504 | `RETRIEVAL_TIMEOUT` | 可重试，不编造回答 |
| 请求过频 | 429 | `RATE_LIMITED` | 显示等待时间 |

## 7. 契约决策与遗留问题

| 问题 | 当前决策 |
| --- | --- |
| 是否对外提供工具执行接口 | 不提供；只允许工作流内部 Tool Gateway |
| Case 列表是否必须 | 必须；否则无法实现“最近会话”和我的 Case |
| Case 事件订阅是否 P0 | 建议 P0；否则审批后的跨角色状态只能轮询 |
| 停止生成如何持久化 | 消息标记 `STOPPED`，保留部分内容，可重试 |
| 审批是否允许带参数修改 | P1；P0 只允许按原参数批准/拒绝 |
| 审计分页 | cursor；按时间和事件 ID 稳定排序 |
| SSE 是否发送模型内部推理 | 不发送；只发送安全步骤标签 |

实现阶段应基于本文件生成实际 OpenAPI 文档，并用 FastAPI 类型和前端生成类型双向校验，避免文档与代码漂移。
