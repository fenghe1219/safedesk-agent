# SafeDesk 设计底稿

> 版本：v0.2  
> 状态：设计评审已通过，M2 分诊与工单已完成本机 Compose 验收
> 依据：`E:\SafeDesk\SafeDesk-完整需求说明书.md`

## 文件索引

| 文件 | 内容 |
| --- | --- |
| `docs/design-system.md` | 色彩、排版、间距、动效、组件和文案规范 |
| `docs/ia-and-flows.md` | 信息架构、角色导航、页面清单、Case 五阶段和核心流程 |
| `docs/data-model-and-state-machines.md` | 实体关系、状态机、事务边界和检查点规则 |
| `docs/openapi-and-sse.md` | API 目录、关键 Schema、SSE 事件和错误契约 |
| `docs/wireframes/case-workspace.md` | Case 工作台三栏布局与各状态卡片 |
| `docs/wireframes/approval-queue.md` | 审批队列、详情抽屉和决定交互 |
| `docs/design-preview/index.html` | 可直接打开的静态视觉预览 |
| `docs/design-preview/preview.png` | Case 工作台与审批页的渲染截图 |

## 当前锁定

- 单人开发，按 6 周收敛 P0；优先保证纵向闭环。
- 模块化单体：Next.js + FastAPI + PostgreSQL/pgvector + Worker。
- 业务数据库是唯一事实源；LangGraph 只负责编排和检查点。
- 中文检索先采用 pgvector + pg_trgm，保留分词适配层。
- 视觉方向为“清朗工作台”：雾白、青绿、细边框、克制动效。
- Admin 可查看审批队列，但不自动拥有审批权。
- Employee 工单入口建议为本人只读；服务端强制资源归属。

## 预览

![SafeDesk 设计预览](design-preview/preview.png)

打开 `docs/design-preview/index.html` 可查看可缩放、可滚动的完整静态稿。

## 当前进度

- M0 已完成：Docker Compose、数据库初始迁移、登录/RBAC、Case 创建与时间线、角色化 Web 外壳。
- M1 已完成：知识文档导入与切分、混合检索、SSE 回答、引用与原文定位、拒答、Case 对话工作台。
- M2 已完成：7 类分诊、P1–P4 优先级、缺失信息追问、工单草稿/确认、工单 CRUD 与流转、处理人推荐、80 条分诊评估集。
- 设计系统、导航、Case 工作台和审批队列底稿继续作为 M3–M4 的实现依据。
- 启动方式、演示账号和验证状态见根目录 `README.md`。

![M0 登录页](design-preview/m0-login.png)

## 下一步

1. M1 已于 2026-11-06 完成本机 Docker Compose 端到端验收。
2. M2 已于 2026-11-06 完成本机 Docker Compose 端到端验收。
3. M3：Tool Gateway、显式工作流与持久化检查点、审批与幂等执行。
