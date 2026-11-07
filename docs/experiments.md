# SafeDesk Agent 实验设计与口径

> 目标：用固定数据、固定配置和可追溯 Run 证明改动有效，而不是只展示“看起来更聪明”的对话。

## 1. 实验原则

1. **固定样本**：优先使用仓库内固定知识集 40 条、分诊集 80 条、安全集 15 条；导入集只用于补充，不替换基线。
2. **固定配置**：一次只改变一个变量；Prompt 版本、模型、温度、Top-K、最低相关度、上下文片段和回答模式都记录在 `EvalRun`。
3. **服务端可复现**：评估复用与线上相同的 Agent Provider、Prompt、检索和本地回退逻辑。
4. **不夸大结论**：样本量小，指标是回归信号，不是公开发表级别的统计结论。
5. **安全优先**：任何“提升通过率”的改动都不能绕过审批、身份覆盖或审计。

## 2. 当前可执行的实验

### E1：RAG 开 / 关消融

**假设**：关闭检索后，模型缺少公司知识依据，检索 Recall@K、引用一致率和答案正确率应下降，拒答率或失败率应上升。

**数据集**：知识问答 40 条固定集。

**控制变量**：Prompt 版本、回答模式 `local`、Top-K、最低相关度、样本集不变。

**唯一变量**：`retrieval_config.enabled`。

```http
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

**预期结果**：

- 基线 `retrieval_recall_at_k > 0`；
- 关闭 RAG 后 `retrieval_recall_at_k = 0`、`retrieval_mrr = 0`；
- `answer_accuracy` 下降，回归门禁把 `retrieval_recall_at_k` 标为阻断指标；
- 具体数值以实际 Run 为准；下表只记录一次本机实测，不作为固定基线。

**2026-11-07 本机实测**（Compose + PostgreSQL，知识集 40 条，Recall 分母 34 条，本地规则 `answer_mode=local`）：

| 变体 | Recall@K | 答案正确率 | 回归门禁 |
| --- | --- | --- | --- |
| 完整 RAG | 97.06% | 92.50% | 基线 |
| 关闭 RAG | 0.00% | 15.00% | 阻断 4 项关键指标 |

这组结果证明检索链路确实影响回答，但样本量仍小，不能外推为生产准确率；重新运行时刻度会因本机状态略有波动。

前端入口：`/evaluations` → 选择知识问答数据集 → “运行 RAG 消融（开 / 关）”。

### E2：本地规则 vs 模型回答

**假设**：配置真实模型后，回答覆盖率和引用一致率可能提升，但延迟、Token 成本和回退率也会变化。

**控制变量**：同一固定集、同一 Prompt、同一检索配置。

**变量**：`model_settings.answer_mode` 或 `provider`。

```json
{"model_settings": {"provider": "local-rules", "answer_mode": "local"}}
```

与：

```json
{"model_settings": {"answer_mode": "auto"}}
```

后者只有在服务端配置了 `LLM_PROVIDER=openai_compatible` 时才真正调用模型；否则自动回退本地规则，并在结果中记录 `fallback_reason`。**不能把未配置模型的 Run 标记为“真实模型效果”。**

### E3：Prompt 版本对比

**假设**：更严格的 grounding / 拒绝规则能降低无依据回答，同时可能降低覆盖率。

**变量**：`prompt_version`。

**观察指标**：`citation_consistency`、`refusal_accuracy`、`answer_accuracy`、`fallback_rate`。

### E4：工具策略与写操作边界

工具策略不是靠“模型自觉”，而是服务端测试：

- 未知工具被拒绝；
- 管理员停用的工具被拒绝；
- 模型伪造 `user_id` 被覆盖为 Case 请求人；
- 写工具只产生 `ActionRequest` / `Approval`，审批前没有 `ToolExecution`；
- 重复审批不重复执行；
- Kill Switch、过期、Case 关闭等条件阻断执行。

这些场景由 `apps/api/tests/test_agent_memory.py` 和 `apps/api/tests/test_actions.py` 覆盖，属于确定性行为测试，不依赖模型随机性。

### E5：记忆与查询改写

**假设**：多轮短追问需要补充 Case 环境/错误码后才能召回正确文档。

**对照**：

- 关闭 `memory_enabled` / `query_rewrite_enabled`；
- 开启本地改写；
- 开启模型改写（配置 Provider 后）。

**观察**：检索命中标题、Recall@K、引用一致率、`query.rewritten` 审计中的原始/改写问题。

## 3. 指标定义

| 指标 | 含义 | 口径 |
| --- | --- | --- |
| `retrieval_recall_at_k` | 期望文档是否出现在 Top-K 检索结果 | 仅统计有 `doc_titles` 的可回答样本 |
| `retrieval_mrr` | 首个正确文档排名的倒数均值 | 未命中记 0 |
| `citation_coverage` | 可回答样本中产生引用的比例 | 分母为可回答样本 |
| `citation_consistency` | 引用文档与期望文档有交集的比例 | 分母为可回答样本 |
| `refusal_accuracy` | 拒答/应回答判断正确的比例 | 分母为全部样本 |
| `answer_accuracy` | 样本级通过率 | 由引用、拒答和文档匹配共同决定 |
| `fallback_rate` | 出现模型回退原因的样本比例 | 本地规则基线通常为 0 |
| `avg_latency_ms` | 检索 + 回答/模型调用平均延迟 | 受本机负载影响 |
| `avg_token_count` | 平均 Token 数 | Provider 返回 usage 时优先使用，否则明确标记估算 |
| `avg_cost_usd` | 平均成本 | 按配置单价计算，不是供应商账单 |

## 4. 结果解读

- **先看样本量**：`metric_sample_sizes` 给出每个指标的实际分母；不要把 15 条安全样本的比例当作总体准确率。
- **先看回归门禁**：关键指标下降超过运行时阈值（默认 3 个百分点）时，`regression_blocked=true`。
- **区分真实与估算**：`usage.estimated=true` 表示 Provider 没有返回 usage，成本是本地估算。
- **区分本地与模型**：查看 `actual.provider`、`actual.model`、`actual.answer_mode` 和 `actual.fallback_reason`。
- **不比较不同数据集**：`/api/eval/compare` 只允许同一数据集上的 Run。

## 5. 复现实验的最小步骤

```powershell
# 1. 启动服务
docker compose up -d --build

# 2. 可选：配置模型（不配置则保持离线基线）
$env:LLM_PROVIDER = "openai_compatible"
$env:LLM_BASE_URL = "http://host.docker.internal:11434/v1"
$env:LLM_MODEL = "qwen2.5:7b"

# 3. 登录评估员账号，在 /evaluations 运行固定集或消融
# 4. 对比 Run，查看逐指标差异和阻断指标
# 5. 抽查逐样本 actual / citations / fallback_reason
```

## 6. 后续可补充

- 对同一配置重复运行 3 次，报告均值与波动；
- 用 paired bootstrap 或 McNemar 检验比较同一批样本上的两个配置；
- 扩大安全集和知识集，加入人工双盲复核；
- 接入真实 IT 工具后，增加“工具执行成功率”和“真实回滚成功率”；
- 对模型输出做结构化约束（JSON Schema / function calling）并比较非法输出率。
