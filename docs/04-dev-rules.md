# 开发规则（Dev Rules）

> 状态：Phase 0 · 自 Phase 1 起强制生效。违反分层/契约纪律的提交直接打回。

## 1. 契约纪律（最高优先级）

1. Phase 1 结束后 `contracts/` 与 `docs/06-tool-contract.md` 一起**冻结**：工具名、入参名、出参字段名、错误码只增不改不删。
2. 需要变更时走书面变更请求：改 `01` 需求 → 升契约次版本号（`1.0.0 → 1.1.0`）→ 同步文档 + 适配 Mock + 通知编排侧。破坏性变更必须升主版本。
3. 出参一律返回**结构化对象**（成功标志 + 数据 + 错误码 + 人类可读消息），禁止裸字符串、禁止抛裸异常到 MCP 层。

## 2. 分层与依赖

1. 依赖方向固定：`entry → server → tools → routers → backends`；`contracts / config / common / observability` 为被依赖方。
2. `tools/` 里禁止出现：Windows API、`mode == "real"` 分支、`import uiautomation`、`import windows_capture`。
3. `backends/mock/` 禁止 import `backends/real/`；两者只共享 `backends/base.py` 的接口。
4. 每个后端实现必须通过同一份 `tests/contract/` 用例（契约测试对两后端参数化），Mock 与 Real 行为差异只允许体现在数据来源与错误分布。

## 3. Mock / Real 隔离

1. Mock 是**一等公民**：开发机全部测试在 Mock 下通过才能合并。
2. Real 专属依赖必须延迟导入（函数内 import），缺依赖时服务仍能在 mock 模式启动，并给出明确错误码（`DEPENDENCY_MISSING`）。
3. Real 后端的每个 Windows 调用点都要有能力探测 + 降级路径 + 显式错误码，禁止 `try: ... except: pass`。
4. Mock 必须支持可复现的异常注入（窗口不存在、超时未完成、结束标记缺失），用于编排侧容错联调。

## 4. 错误码与日志

1. 错误码集中定义在 `contracts/errors.py`，命名 `UPPER_SNAKE`，一期清单：
   `OK` / `WINDOW_NOT_FOUND` / `CONTROL_NOT_FOUND` / `SEND_FAILED` / `OUTPUT_TIMEOUT` / `NOT_COMPLETED` / `RULES_INVALID` / `DEPENDENCY_MISSING` / `INTERNAL_ERROR` / `MODE_MISMATCH`。
2. 日志：结构化（`event` + `win_key` + `correlation_id` + 耗时），默认写 `logs/`，按天滚动；禁止在日志里打印完整 prompt 正文（只打长度 + 前 40 字），避免把客户内容落盘。
3. 每个工具调用必须记录：入参摘要、后端类型、耗时、错误码、结果状态。
4. 超时与“未完成”是**正常状态**，用返回字段表达，不能打成 ERROR 级日志噪音。

## 5. 代码风格

1. Python 3.12，全量类型注解，`ruff` + `mypy --strict`（`backends/real` 里 Windows 库可局部放宽）。
2. `snake_case` 文件与函数、`PascalCase` 类、常量 `UPPER_SNAKE`；结束标记只从 `contracts/constants.py` 取，禁止硬编码字符串。
3. 一文件一职责，超过 ~300 行拆分；函数超过 ~50 行先想是否该拆。
4. 中文注释可以，但只在“为什么”层写；禁止用注释复述代码。
5. 不用 `print`，一律走 logger。

## 6. 测试纪律

| 层 | 范围 | 依赖 GUI | 门禁 |
| --- | --- | --- | --- |
| `tests/unit` | 纯函数、解析、重试、文本清洗 | 否 | 必过 |
| `tests/contract` | 四工具入参出参契约，Mock/Real 双参数化 | 否（Real 用假驱动替身） | 必过 |
| `tests/e2e` | 真起服务 + MCP 客户端联通（stdio/SSE + Inspector 用例） | Mock 必过；Real 仅工作机手动 | Mock 必过 |

- 新增工具或字段必须同时加契约测试。
- 真实 Windows 相关代码在开发机用“假驱动（fake driver）”做单测，接口与真驱动一致。
- 工作机人工验证清单写在 `09-deploy-and-packaging.md`，每次发版勾选。

## 7. 配置与安全

1. `config.yaml` 只放非敏感项；任何密钥（如未来接 API）走环境变量。
2. 服务默认只监听 `127.0.0.1`；需要局域网访问必须显式配 `host: 0.0.0.0` 并写清风险（SSE 无内建鉴权，一期默认加一个可选的 `auth_token`）。
3. 不抓包、不逆向、不注入客户端进程；只允许 UIA 与系统原生窗口 API。违反即功能直接砍掉。
4. 不采集、不上传用户聊天内容；日志脱敏规则见 §4.2。

## 8. 版本与提交

1. 语义化版本 `MAJOR.MINOR.PATCH`；契约破坏性变更升 MAJOR。
2. 提交信息：`<scope>: <what>` 单行 + 必要时正文说明“为什么”；scope 用目录名（`contracts` / `tools` / `backends/real` / `docs`）。
3. 一次提交只做一件事；文档与代码同步变更放同一提交。
4. 分支：`main` 保持可跑（Mock 全绿），开发在 `feat/*`，阶段结束合并并打 tag（`phase1-contract-frozen` 等）。
5. `.ai-workspace-runtime/tmp/`、`devtools/tmp/`、`logs/`、产物文件一律 gitignore。

## 9. 交付卫生

1. 打包前必须：Mock 全测试通过 → 配置模板齐全 → `window_rules.json` 带示例与字段注释 → README 与 `09` 步骤一致。
2. 包里不得含：本机绝对路径、调试探针、临时日志、`config.local.yaml`。
3. 交付物只放最终文件；中间脚本、探测数据不进交付目录（按系统补充上下文要求写入临时目录）。
