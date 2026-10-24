# 分层图 L0：编排层 ↔ MCP 服务 ↔ 客户端

> 状态：P0 · 本轮只落 L0 这一层。L1–L4 见 `00-doc-map.md` §2，按阶段逐轮补，不在此文件向下展开。

## L0-1 纵向依赖

```
[上层编排层] DSH / Cherry Studio / LangGraph
      │  只做：拆任务、判流转、汇总结果；不做识图
      │  MCP：SSE（主推）/ stdio
      ▼
┌─────────────────────────────────────────────────────┐
│ [本项目] DesktopAI-Orchestrator                     │
│                                                     │
│  ① 传输层  entry/    SSE 入口 │ stdio 入口           │
│           │                                         │
│  ② 装配层  server/   Server 实例 · 工具注册 · 生命周期│
│           │                                         │
│  ③ 工具层  tools/    4 个工具（契约边界，零业务）     │
│           │                                         │
│  ④ 路由层  routers/  mode → 后端实例                 │
│        ┌──┴──┐                                      │
│  ⑤a mock 后端  │  ⑤b real 后端                       │
│   零 GUI 依赖  │  UIA + DXGI 捕获                    │
└────────────────┼────────────────────────────────────┘
                 │ 仅 Windows 原生 API（不抓包、不逆向）
                 ▼
[工作机客户端] Trae / Qoder / WorkBuddy（Electron）
```

## L0-2 横向支撑

```
contracts/      入参·出参·错误码·常量   ← 被所有层依赖，自身不依赖上层
config/         config.yaml + window_rules.json（外置、可热重载）
common/         错误、重试、文本清洗
observability/  结构化日志、耗时、correlation_id
```

## L0-3 两条运行态（同一工具契约）

| 路径 | 开发机 | 工作机 |
| --- | --- | --- |
| 编排层 → MCP → **mock 后端** → 静态数据 | ● 主用 | 备用 |
| 编排层 → MCP → **real 后端** → UIA/捕获 → 三客户端 | — | ● 主用 |

## 下一层

- L1 调用时序（`send_prompt` → 轮询 `fetch_output` → 结束标记）：P1 落 `02-tool-call-sequence.md`
