# 决策记录（Decision Log / ADR 简版）

> 状态：持续更新。每条决策记录“为什么”，实现变化不作为修改历史。
> 格式：编号 / 日期阶段 / 决策 / 理由 / 代价 / 状态

## ADR-001 语言与运行时：Python 3.12
- 阶段：P0
- 决策：服务用 Python 实现，`mcp` 官方 SDK + Windows UIA 生态（`uiautomation`/`comtypes`）。
- 理由：UIA 与 DXGI 窗口捕获的 Python 封装最成熟（`windows-capture`、`uiautomation`），PyInstaller 可打单文件。
- 代价：工作机需要 Python 或 exe；类型严谨度不如 TS。
- 状态：已定

## ADR-002 src-layout + 分层目录
- 阶段：P0
- 决策：`src/desktop_ai_orchestrator/` 下按 `entry/server/tools/routers/contracts/config/backends/common/observability` 分区。
- 理由：测试期不污染路径；Mock/Real 物理隔离，便于“开发机零 GUI 依赖”硬约束落地。
- 代价：多一层目录深度。
- 状态：已定

## ADR-003 契约先行并冻结
- 阶段：P0 起草 / P1 冻结
- 决策：先定四工具入参出参与错误码，冻结后只增不改。
- 理由：编排侧（DSH）与 MCP 服务并行开发，必须有稳定边界；Electron 客户端版本变动只影响后端，不该破契约。
- 代价：早期需要更谨慎的设计评审。
- 状态：草案

## ADR-004 出参统一包一层 `data` + `error_code`
- 阶段：P0
- 决策：所有工具返回 `{ok, error_code, message, backend, correlation_id, elapsed_ms, data}`。
- 理由：编排器可只凭 `error_code` 决策，避免解析业务字段判错；`backend` 字段让 Mock/Real 一眼可辨。
- 代价：返回体略大。
- 状态：待 P1 确认

## ADR-005 “未完成”不是错误
- 阶段：P0
- 决策：`fetch_output` 用 `status`（`completed/generating/timeout/idle`）表达等待态，`ok=true`。
- 理由：AI 生成耗时长，把等待打成错误会让编排侧把正常流程当失败重试，浪费免费额度。
- 代价：编排侧必须实现轮询循环。
- 状态：已定

## ADR-006 控件规则全部外置 `window_rules.json` + 策略降级链
- 阶段：P0
- 决策：控件定位不写死代码，规则里每个目标给有序 `strategies`，逐条降级。
- 理由：Electron 壳 UIA 控件 ID 随版本变化，且工作机才能采集；降级链可延长规则寿命。
- 代价：规则文件需要工作机人工采集与维护。
- 状态：已定

## ADR-007 一期单窗口串行，不做并发
- 阶段：P0
- 决策：每个客户端只支持一个窗口实例，工具调用串行处理。
- 理由：先保证单链路可靠；并发调度、额度池分配属于编排侧策略，且会显著放大 UIA 竞态问题。
- 代价：无法同时压满三家额度（后续扩展）。
- 状态：已定

## ADR-008 不做识图 / OCR / 坐标点击
- 阶段：P0
- 决策：主判定链只用 UIA 文本；画面捕获仅作降级取证。
- 理由：用户明确要求上层不启用视觉识图以控成本；OCR/坐标点击脆弱且会引入第二套失败模型。
- 代价：若某客户端 UIA 完全不可用，需走变更请求。
- 状态：已定（变更需书面记录）

## ADR-009 Real 依赖延迟导入
- 阶段：P0
- 决策：`backends/real` 内 Windows 库在函数内 import，缺失时返回 `DEPENDENCY_MISSING`。
- 理由：开发机（无这些库/非目标环境）必须能以 mock 模式启动并跑 CI。
- 代价：import 位置不统一，需要 lint 规则约束。
- 状态：已定

## ADR-010 传输双协议共用一套业务实现
- 阶段：P0
- 决策：SSE 与 stdio 仅入口不同，工具与后端完全共用。
- 理由：避免两套行为漂移；换工作台只改连接方式。
- 代价：入口需要处理两种生命周期/退出语义。
- 状态：已定

## 待定项（Open Questions）

| # | 问题 | 影响 | 何时决 |
| --- | --- | --- | --- |
| Q1 | SSE 是否默认开 `auth_token` | 局域网暴露安全 | P1 前 |
| Q2 | 是否需要 PyInstaller 单文件 exe（vs 直接拷贝文件夹 + 工作机装 Python） | 交付形态 | P3 前 |
| Q3 | 结束标记是否允许按 client 覆写（规则内已有字段，是否保留） | 契约字段 | P1 冻结前 |
| Q4 | 产物落盘是 MCP 提供可选写文件工具，还是完全交给编排侧 | 范围边界 | P5 前 |
| Q5 | 是否需要“发送前清空输入框”策略 | 发送可靠性 | P2 实测后 |
| Q6 | 客户端半路弹窗（升级提示、额度用尽）如何中断任务 | 容错 | P2 实测后 |
