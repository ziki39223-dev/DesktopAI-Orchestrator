# DesktopAI-Orchestrator（桌面 AI 调度 MCP 服务）

> 底层机械手：独立、可打包迁移的 MCP 服务，用 Windows 原生 UIA + 窗口捕获，后台操控本机
> Trae / Qoder / WorkBuddy 三款 Electron 客户端，最大化利用三家免费额度。
> 上层编排器（DSH 为主）与本项目完全解耦，本包只含 MCP 服务。

**当前状态：前期准备阶段（Phase 0）。** 已建立目录分区与文档体系，未编写业务代码。
下一步等待指令进入阶段 1（脚手架 & 工具契约冻结）。

## 一句话边界

| 属于本项目 | 不属于本项目 |
| --- | --- |
| MCP 服务源码、工具契约、Mock/Real 双后端、窗口规则配置、启动脚本、打包流程 | DSH / Cherry Studio / LangGraph 的 Agent 角色 Prompt、流水线 DAG、人工审批节点、毕设产物 md |

## 文档索引

| 文档 | 作用 |
| --- | --- |
| [docs/00-doc-map.md](docs/00-doc-map.md) | 文档规划：清单、职责、编写顺序、状态 |
| [docs/01-requirements-baseline.md](docs/01-requirements-baseline.md) | 需求基线：目标、边界、约束、验收口径 |
| [docs/02-architecture.md](docs/02-architecture.md) | 架构说明：分层、依赖方向、运行模式 |
| [docs/03-directory-layout.md](docs/03-directory-layout.md) | 目录分区：每个目录职责与归属阶段 |
| [docs/04-dev-rules.md](docs/04-dev-rules.md) | 开发规则：契约冻结、分层约束、Mock/Real 隔离、日志与错误码、提交规范 |
| [docs/05-dev-plan.md](docs/05-dev-plan.md) | 开发计划：阶段、任务拆解、验收标准、风险 |
| [docs/06-tool-contract.md](docs/06-tool-contract.md) | 工具契约 v1.0.0（已冻结，只增不改不删） |
| [docs/07-decision-log.md](docs/07-decision-log.md) | 决策记录（ADR 简版）与待定项 |
| [docs/10-mcp-inspector-testing.md](docs/10-mcp-inspector-testing.md) | 联调手册：demo 客户端 / Inspector / 异常路径用例 |
| [docs/diagrams/01-layers.md](docs/diagrams/01-layers.md) | 分层图 L0 |
| [docs/diagrams/02-tool-call-sequence.md](docs/diagrams/02-tool-call-sequence.md) | 分层图 L1：调用时序 + fetch 状态机 |

## 环境基线

- 开发机：无 DSH / Trae / Qoder / WorkBuddy，只做编码、Mock 调试、版本管理、打包
- 工作机：DSH + Trae / Qoder / WorkBuddy，MCP 服务部署于此，跑 Real 真机模式
- 运行时：Python 3.12（`requirements.txt` 交付依赖清单，可选 PyInstaller 单文件 exe）

## 目录分区（已建立，代码待填）

```
src/desktop_ai_orchestrator/
  entry/        SSE 入口 · stdio 入口
  server/       Server 装配 · 工具注册 · 生命周期
  tools/        四工具（契约边界，零业务）
  routers/      mode → 后端选择
  contracts/    入参/出参/错误码/常量（唯一真源）
  config/       yaml / json 加载与校验
  backends/mock/   零 GUI 依赖
  backends/real/   UIA + DXGI 捕获
  common/       错误、重试、文本清洗
  observability/结构化日志、耗时、追踪
config/  scripts/  tests/{unit,contract,e2e}  devtools/uia/  docs/diagrams/
```

各目录职责与禁忌见 [docs/03-directory-layout.md](docs/03-directory-layout.md)。

## 下一步（等指令）

P1 开工前需确认四件事，详见 [docs/05-dev-plan.md](docs/05-dev-plan.md) 末尾“待确认项”：
是否直接实现到 MCP Inspector 可调用、是否 `git init`、是否必须 PyInstaller 单文件 exe、SSE 是否默认开 `auth_token`。
