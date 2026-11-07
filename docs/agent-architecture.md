# SafeDesk bounded agent 架构

> 适用范围：当前 `main` 分支的 AI Agent 扩展。默认仍可完全离线运行；只有配置 OpenAI-compatible Provider 后才会调用外部模型。

## 1. 设计目标

SafeDesk 不是“让模型自由调用一切工具”的开放式 Agent，而是一个**有界自治（bounded autonomy）**的企业服务台 Agent：

- 模型负责理解问题、提出只读诊断和生成回答；
- 服务端负责工具白名单、身份注入、参数校验、审批和执行；
- 写操作永远不能由模型直接完成；
- 每次模型调用、工具拒绝和回退都写入追加式审计；
- 模型不可用时，系统回退到可解释的本地规则基线。

关键原则：**模型可以建议，服务端决定是否允许；写操作必须经过人工审批。**

## 2. 分层结构

```text
Next.js Case 工作台
  └─ POST /api/cases/{id}/messages（SSE）
       └─ Conversation Orchestrator
            ├─ Memory Service         Case 事实 / 用户偏好
            ├─ Query Rewrite          本地兜底 / 模型改写
            ├─ Retrieval               ACL 过滤 + 词法/哈希向量检索
            ├─ Agent Runtime          OpenAI-compatible Provider
            │    ├─ PromptVersion     当前激活的系统提示词
            │    ├─ Decision Loop     严格 JSON，最多 N 步
            │    ├─ Policy Engine     白名单 / 启用状态 / 参数校验 / 身份覆盖
            │    └─ Read Tools        服务端执行 observation
            ├─ Action Service         写工具只生成 ActionRequest
            ├─ Approval State Machine 人工批准 / 拒绝 / 过期
            ├─ Tool Gateway           幂等执行 + 复核
            └─ Audit                  追加式事件与请求追踪
```

对话主链路位于 `apps/api/app/services/conversation.py`，Agent 循环位于 `apps/api/app/services/agent.py`，Provider 适配位于 `apps/api/app/services/llm.py`。

## 3. 决策循环

一次 Agent 运行最多调用模型 `min(AGENT_MAX_MODEL_CALLS, runtime.max_steps)` 次。每一轮模型必须返回严格 JSON：

```json
{
  "answer": "给用户的回答，可包含 [1] 引用标记",
  "citation_indices": [1],
  "refused": false,
  "tool_call": {
    "name": "get_vpn_status",
    "arguments": {"user_id": "model-supplied-value"},
    "rationale": "为什么需要这个工具"
  }
}
```

`tool_call` 可以为 `null`。服务端按以下顺序处理：

1. 解析 JSON；非法输出记录 `agent.output_rejected` 并回退本地规则。
2. 若没有工具提议，结束循环并返回回答。
3. 校验工具是否在白名单、是否被管理员启用。
4. 只读工具：服务端覆盖 `user_id`、校验参数、执行工具，把 observation 追加回模型上下文，继续下一轮。
5. 写工具：服务端只构造 `ToolProposal`，由 Action Service 创建 `ActionRequest` 与 `Approval`，**不调用 Tool Gateway**。
6. 未知工具、禁用工具、越权写操作记录 `agent.tool_rejected`，并给模型一次纠错机会。

回答中的引用索引由模型选择，但标题、版本、页码、章节、原文快照和引用对象全部由服务端从检索结果重新组装。模型不能伪造引用来源。

## 4. 信任边界

| 能力 | 模型 | 服务端 |
| --- | --- | --- |
| 理解问题、提出诊断 | 可以 | 提供检索上下文与工具目录 |
| 选择只读工具 | 可以提议 | 白名单、启用状态、参数 Pydantic 校验 |
| 指定 `user_id` | 可以填写 | 强制覆盖为 Case 请求人或当前用户 |
| 执行只读工具 | 不可以 | 执行并回传 observation |
| 执行写工具 | 不可以 | 只创建 Action/Approval，审批后才执行 |
| 生成引用 | 只选择序号 | 从数据库重建引用快照 |
| 修改系统提示词 | 不可以 | 读取当前激活的 `PromptVersion` |
| 关闭审计或跳过审批 | 不可以 | 状态机与权限中间件强制校验 |

这套边界对应真实的 Agent 风险：提示注入、工具参数篡改、身份冒用、越权写操作和引用伪造。模型输出被视为**不可信输入**，而不是权限来源。

## 5. 分层记忆

记忆表为 `memory_entries`，按作用域隔离：

| 作用域 | 绑定 | 典型内容 | 生命周期 |
| --- | --- | --- | --- |
| `CASE` | `case_id` + `user_id` | 使用环境、错误码、Case 主题 | 跟随 Case |
| `USER` | `user_id` | 回答详细/简洁偏好 | 180 天 TTL |

写入只发生在 Case 请求人本人的消息上；读取只返回当前用户可见的 Case 记忆和自己的用户偏好。删除接口会再次校验 `entry.user_id`，跨用户删除返回 404。所有写入与删除都有审计事件。

记忆不是无限对话历史。它只保存低风险、可解释、可删除的事实和显式偏好，避免把整段对话或敏感信息永久注入后续请求。

## 6. 多轮查询改写

短问题或包含“还是不行”“这个”“继续”等指代的追问，会先改写为可检索的独立问题：

- 模型可用：模型只输出 `{"query": "..."}`，不得引入未出现的事实；
- 模型不可用或输出非法：本地规则把 Case 主题、环境和错误码拼入查询；
- 改写结果、是否使用模型、回退原因和记忆数量写入 `query.rewritten` / `retrieval.completed` 审计。

## 7. 失败与回退

| 场景 | 行为 |
| --- | --- |
| `LLM_PROVIDER=disabled` | 直接使用本地 `extractive-rag-v1`，不产生模型调用 |
| 模型超时 / HTTP 错误 / 空响应 | 记录 `agent.fallback`，回退本地规则 |
| 模型输出非 JSON / 引用越界 | 记录 `agent.output_rejected`，回退本地规则 |
| 模型回答无合法引用 | 回退本地规则，避免无依据回答 |
| 达到最大模型调用次数 | 返回已有回答并标记 `AGENT_STEP_LIMIT` |
| 写提议参数非法 | 拒绝并记录 `agent.tool_rejected` |
| 工具被管理员停用 | 拒绝工具调用，模型可基于已有信息继续回答 |

## 8. 为什么不引入 LangGraph 运行时

当前工作流的节点少、状态机明确，且业务数据库是唯一事实源。用显式状态机和数据库检查点已经能表达：

- 提议动作 → 等待审批 → 执行 → 复核 → 解决；
- 进程重启后的状态恢复；
- 幂等、过期、Kill Switch 和权限校验。

引入通用图运行时会增加一层与业务状态重复的事实源，也会让审计和恢复更难解释。这里的取舍不是“工作流被淘汰”，而是**用最小的编排机制换取可验证性和可运维性**。如果未来出现多 Agent 协作、动态子图或长任务队列，再评估专用编排框架。

## 9. 可观测性

关键审计事件：

- `agent.model_call`：模型、Prompt、延迟、Token、成本、是否估算、工具提议；
- `agent.tool_rejected`：工具名、拒绝码、参数键；
- `agent.output_rejected`：非法输出类型；
- `agent.completed`：步数、只读 observation 数、写提议、回退原因、trace；
- `agent.fallback`：回退原因、Provider、模型；
- `memory.written` / `memory.deleted`：记忆作用域与键；
- `query.rewritten`：原始问题、改写问题、是否使用模型；
- `action.proposed` / `approval.requested` / `tool.executed`：写操作全链路。

## 10. 当前限制

- 工具实现是 Mock，不代表真实 IT 系统集成；
- 默认检索是词法匹配 + 本地哈希向量，不是神经 Embedding；
- 未配置模型时所有指标都是本地规则基线，不能宣称真实 LLM 效果；
- 固定安全集只有 15 条，适合回归，不足以支撑统计显著性结论；
- 尚未实现多 Agent 协作、长期任务队列和自动知识写回。
