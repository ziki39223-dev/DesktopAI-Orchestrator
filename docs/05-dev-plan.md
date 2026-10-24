# 开发计划（Dev Plan）

> 状态：Phase 0 定稿，等待用户指令后才进入阶段 1。本文只写“做什么 + 怎么算做完”，实现细节归代码与 `06` 契约。
> 约定：一个阶段一个 tag；阶段 DoD 全绿才允许进入下一阶段。

## 0. 阶段总览

| 阶段 | 名称 | 环境 | 产出 | 阻塞后续 |
| --- | --- | --- | --- | --- |
| P0 | 前期准备（**本轮已完成**） | 开发机 | 目录分区、文档体系、开发规则、计划、契约草案 | 是 |
| P1 | 脚手架 & 契约定义 | 开发机 | 可跑的 Mock MCP 服务（SSE + stdio）+ 冻结契约 + Inspector 用例 | 是 |
| P2 | 真机后端模块 | 开发机编码 / 工作机验证 | UIA 驱动、捕获模块、window_rules 结构、异常与重试 | 是 |
| P3 | 打包与迁移适配 | 开发机打包 → 工作机 | 可拷贝包 / 可选 PyInstaller exe + 采集填规则 + Real 联通 | 是 |
| P4 | 对接编排工作台（DSH） | 工作机 | SSE 接入、三角色分工、DAG 联调（配置在编排侧，不入本包） | 否 |
| P5 | 优化容错交付 | 双机 | 超时/轮询/日志持久化、产物落盘、文档终稿 | — |

## P0 · 前期准备（已完成）

交付：
- [x] 目录分区（`src/` src-layout + `config/` `scripts/` `tests/` `docs/` `devtools/`）
- [x] 文档规划 `00`，需求基线 `01`
- [x] 架构 L0 `02` + 分层图 `diagrams/01-layers.md`
- [x] 目录职责 `03`，开发规则 `04`，开发计划 `05`，契约草案 `06`，决策记录 `07`
- [x] README 门面

DoD：用户确认目录与文档结构可接受 → 放行 P1。
**未做**：任何业务代码、依赖安装、git 初始化（等确认后一并做）。

## P1 · 脚手架 & 契约定义（预计 1 个工作单元）

任务：
1. `pyproject.toml` + `requirements.txt`（`mcp`、`pydantic`、`pyyaml`；Real 依赖单列 `requirements-real.txt`）。
2. `contracts/`：`tools.py`（四工具入参出参）、`errors.py`（错误码）、`constants.py`（结束标记）。
3. `backends/base.py` 后端协议；`backends/mock/` 完整实现（含延迟与失败注入）。
4. `routers/backend_router.py`：`mode` → 后端实例。
5. `server/app.py`：注册四工具；`entry/sse.py`、`entry/stdio.py` 双传输入口。
6. `config/config.yaml` 模板 + `config/window_rules.example.json` 模板 + 加载校验。
7. `scripts/start_sse.bat`、`start_stdio.bat`。
8. `tests/contract/` 四工具双后端参数化用例；`tests/e2e/` 起服务联通用例。
9. **契约冻结**：`06` 定稿，打 tag `phase1-contract-frozen`。

DoD：
- 开发机 `python -m desktop_ai_orchestrator.entry.sse` 与 `...stdio` 均可启动，mock 模式零 GUI 依赖。
- MCP Inspector 能列出并调用四工具，返回结构符合 `06`。
- `pytest` 全绿（unit + contract + e2e，均 Mock）。
- 契约冻结评审通过。

## P2 · 真机后端模块（开发机编码，真机验证）

任务：
1. `backends/real/window_enum.py`：EnumWindows + 标题/类名关键字匹配 `window_rules.json`，产出 `win_key`。
2. `backends/real/uia_driver.py`：定位输入框（多策略）、SetValue 写入、触发发送、读输出区文本。
3. `backends/real/capture.py`：DXGI / GraphicsCapture 窗口捕获（后台/最小化三态实测）。
4. `backends/real/resolver.py`：规则→控件路径解析 + 重试 + 版本校验。
5. 异常闭环：`WINDOW_NOT_FOUND` / `CONTROL_NOT_FOUND` / `SEND_FAILED` / `OUTPUT_TIMEOUT` / `NOT_COMPLETED`。
6. `devtools/uia/` 采集辅助脚本（只读探测，输出 json 片段供人工确认）。

DoD：
- 开发机：Real 模块可 import（缺依赖给 `DEPENDENCY_MISSING`），假驱动单测通过。
- 工作机：三客户端各能 `list_target_windows` 命中、`send_prompt` 成功写入并触发发送、`fetch_output` 读到含结束标记的完整结果，至少 1 次全流程。
- 捕获三态结论回填 `01` §10 附录。

## P3 · 打包与迁移适配（关键交付闸）

任务：
1. 打包脚本：文件夹打包（默认）+ 可选 PyInstaller 单文件 exe（`--onefile`，Real 依赖打进去）。
2. 写 `09-deploy-and-packaging.md`：拷贝清单、工作机 Python 判定、首次启动、Inspect.exe 采集步骤、规则回填示例。
3. 工作机实操：采集三客户端控件路径 → 填 `window_rules.json` → `reload_window_rules` 验证热重载。
4. 清空环境复验：模拟“只拿到压缩包”的新机器，按文档从零跑通。

DoD：
- 工作机仅按文档操作即可跑通 Real，无需开发机介入。
- 规则热重载生效，无需重启服务。
- 包内无绝对路径、无本机日志、无 `config.local.yaml`。

## P4 · 对接上层编排工作台（配置在编排侧）

任务（本项目只提供方法说明与联通验证，不产出 DSH 配置）：
1. `11-integration-dsh.md`：SSE 地址、连接参数、工具可见性核对、stdio 兜底方案。
2. 三角色分工**说明**（Trae 架构/开题、Qoder 评审、WorkBuddy 文献）+ 流水线节点与工具映射表。
3. 与编排侧共同做一次全链路：Trae 出大纲 → WorkBuddy 出综述 → Qoder 出评审 → Trae 汇总校验。
4. 记录人工审批停点对工具调用的影响（暂停后是否需要重读输出）。

DoD：四段式闭环在 DSH 里跑通一次，编排侧全程无识图、无人工粘贴。

## P5 · 优化、容错、交付

1. 超时与轮询策略参数化（默认值由 P2 实测耗时回填）；轮询退避。
2. 日志持久化 + 任务 `correlation_id` 贯穿；日志脱敏校验。
3. 状态标记与产物落盘（工具返回产物指针，落盘由编排侧决定，本包只提供可选写文件能力）。
4. `12-troubleshooting.md`、`13-changelog.md`、README 终稿。
5. 回归：Mock 全测试 + 工作机 Real 冒烟清单。

DoD：连续 3 次全链路无人工干预成功；失败场景均返回结构化错误码；文档与代码一致。

## 风险与依赖

| 风险 | 触发阶段 | 缓解 |
| --- | --- | --- |
| Electron UIA 控件不可访问（整棵 UI 树被封） | P2 | 提前在工作机做 15 分钟可行性探针；不可行则提变更（坐标+OCR 兜底需重新评估成本） |
| 客户端版本更新导致规则失效 | P2/P3 起长期 | 规则带 `client_version` + 采集日期；`reload_window_rules` 热重载 |
| 工作机环境（Python/权限）不确定 | P3 | 优先 PyInstaller 单文件；文档给双路线 |
| 免费额度限流导致长等待 | P2 起 | `fetch_output` 超时+未完成状态分离，编排侧循环 |
| 开发机无法验证 Real | P2 | 假驱动单测 + 工作机验证清单，不阻塞编码 |

## 里程碑

| Tag | 含义 |
| --- | --- |
| `phase1-contract-frozen` | 契约冻结，编排侧可并行开发 |
| `phase2-real-backend` | Real 后端可用 |
| `phase3-packaged` | 可迁移交付包 |
| `v1.0.0` | 闭环验收通过 |

## 待确认项（开工前）

1. P1 是否需要我直接实现到“Inspector 可调用”的程度，还是先只落空壳 + 契约？
2. 是否初始化 git 仓库（`git init` + 首次提交）？
3. PyInstaller 单文件 exe 是必须项还是可选加分项？
4. SSE 是否启用可选 `auth_token`（工作机局域网暴露时的最低防护）。
