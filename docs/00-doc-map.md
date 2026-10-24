# 文档规划（Doc Map）

本文件定义项目文档体系。规则：**先定职责再写内容**，每份文档只承担一件事，避免需求/设计/计划互相抄。

## 1. 文档清单与状态

| 编号 | 文档 | 职责（唯一） | 读者 | 何时写 | 状态 |
| --- | --- | --- | --- | --- | --- |
| 00 | `00-doc-map.md` | 文档体系本身：清单、职责、顺序 | 全体 | Phase 0 | ✅ 已完成 |
| 01 | `01-requirements-baseline.md` | 需求基线：目标、范围、约束、验收口径 | 全体 | Phase 0 | ✅ 已完成 |
| 02 | `02-architecture.md` | 分层、依赖方向、运行模式、关键流程 | 开发 | Phase 0 | ✅ 已完成（L0 概览，细节待阶段 2 补） |
| 03 | `03-directory-layout.md` | 目录分区与文件归属 | 开发 | Phase 0 | ✅ 已完成 |
| 04 | `04-dev-rules.md` | 编码/工程规则、契约纪律、提交规范 | 开发 | Phase 0 | ✅ 已完成 |
| 05 | `05-dev-plan.md` | 阶段任务拆解、验收标准、里程碑 | 全体 | Phase 0 | ✅ 已完成 |
| 06 | `06-tool-contract.md` | MCP 工具入参/出参契约（唯一真源，已冻结） | 开发 + 编排侧 | Phase 0 起草 / Phase 1 冻结 | ✅ v1.0.0 已冻结 |
| 07 | `07-decision-log.md` | 决策记录（ADR 简版）+ 待定项 | 全体 | 持续 | 🟡 持续更新 |
| 08 | `08-window-rules-guide.md` | window_rules.json 字段说明 + Inspect.exe 采集教程 | 工作机操作者 | Phase 3 前 | ⬜ 未开始 |
| 09 | `09-deploy-and-packaging.md` | 开发机打包、工作机迁移部署、验证清单 | 工作机操作者 | Phase 3 | ⬜ 未开始 |
| 10 | `10-mcp-inspector-testing.md` | MCP 联调手册：demo 客户端 + Inspector + 异常路径用例 | 开发 | Phase 1 | ✅ 已完成（Mock 部分） |
| 11 | `11-integration-dsh.md` | 对接 DSH：SSE 连接、角色分工、流水线对接**说明**（不写配置内容） | 编排侧 | Phase 4 | ⬜ 未开始 |
| 12 | `12-troubleshooting.md` | 常见故障：窗口找不到、控件错位、超时、捕获黑屏 | 全体 | Phase 5 | ⬜ 未开始 |
| 13 | `13-changelog.md` | 版本变更记录 | 全体 | Phase 5 起 | ⬜ 未开始 |

## 2. 图文档（分层产出，禁止一次性画满）

`docs/diagrams/` 下按层编号，每层一个文件，禁止把系统全图塞进一份文档：

| 文件 | 层级 | 内容 | 状态 |
| --- | --- | --- | --- |
| `01-layers.md` | L0 | 编排层 ↔ MCP 服务 ↔ 三客户端 的分层与依赖方向 | ✅ 本轮完成 |
| `02-tool-call-sequence.md` | L1 | send_prompt / fetch_output 一次调用时序 + 状态机 | ✅ 已完成 |
| `03-backend-routing.md` | L2 | 工具路由层 → Mock / Real 后端分派 | ⬜ Phase 1 |
| `04-real-backend-internals.md` | L3 | UIA 定位、写入、读取、捕获内部结构 | ⬜ Phase 2 |
| `05-task-state-machine.md` | L4 | 任务提交→轮询→结束标记→产物落盘状态机 | ⬜ Phase 5 |

## 3. 编写顺序与门禁

1. Phase 0（本轮）：00 → 01 → 02(L0) → 03 → 04 → 05 → 06 草案 → 07。**门禁：用户确认后可进入阶段 1。**
2. Phase 1：06 定稿冻结 → 10（Inspector 用例）→ 02 的 L1/L2 图。
3. Phase 2：04 图 → 08（采集教程，等工作机实测数据回填）。
4. Phase 3：09 → 12 初版。
5. Phase 4：11（只写对接方法，不写 Agent Prompt / DAG）。
6. Phase 5：13 → 12 补全 → README 终稿。

## 4. 文档纪律

- 需求变更只改 `01`，然后同步 `06` 契约与 `05` 计划；禁止在多份文档里各写一遍需求。
- 契约以 `06` + 代码 `contracts/` 为唯一真源，文档与代码不一致时以冻结后的契约为准，并回改文档。
- 每份文档头部保留 `状态` 与 `最后更新阶段`，避免“看着像终稿其实是草稿”。
