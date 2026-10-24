# MCP 联调手册（Inspector + 自带客户端）

> 状态：P1 · 覆盖 Mock 模式全流程；Real 模式的验证清单见 `09-deploy-and-packaging.md`（P3 编写）。

## 1. 三种联调方式

| 方式 | 命令 | 适合 |
| --- | --- | --- |
| 自带 demo 客户端（最快） | `python scripts/mcp_client_demo.py stdio` | 开发机日常自测、CI |
| SSE 服务 + demo 客户端 | `scripts\start_sse.bat 8765 mock` 再 `python scripts/mcp_client_demo.py sse` | 验证网络模式 |
| MCP Inspector（官方 GUI） | `npx @modelcontextprotocol/inspector` | 可视化看 schema、手动点调用 |

## 2. 前置

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

`pip install -e .` 是为了让 `python -m desktop_ai_orchestrator.entry stdio` 在任意工作目录可用；
不装也可以，但需保证 `PYTHONPATH` 指向 `src`。

## 3. stdio 方式接 Inspector

Inspector 里选 **STDIO**，填：

```
Command:  python
Arguments: -m desktop_ai_orchestrator.entry stdio --config config/config.yaml
```

要点：
- 不要往 `Arguments` 里传 `--log-dir ""` 这类空值参数，Inspector 会当成空字符串转义出错；
  需要关文件日志时改 `config.yaml` 的 `log_dir: ""`。
- stdio 下日志只写 stderr，Inspector 的日志面板能看到，不会污染协议。

## 4. SSE 方式接 Inspector

先启动服务：

```bat
scripts\start_sse.bat 8765 mock
```

看到 `SSE 端点：http://127.0.0.1:8765/sse` 后，Inspector 里选 **SSE**，填：

```
URL: http://127.0.0.1:8765/sse
```

局域网访问：`config.yaml` 里 `server.host: 0.0.0.0`，并建议同时设置 `server.auth_token`。

## 5. 四个工具的手动验证步骤（Mock 模式）

按顺序点，每一步应看到对应结果：

| 步骤 | 工具 | 入参 | 期望 |
| --- | --- | --- | --- |
| 1 | `list_target_windows` | `include_unavailable=false` | `ok=true`，`data.windows` 三条，`backend=mock` |
| 2 | `send_prompt` | `win_key=trae`，`prompt=测试` | `ok=true`，`data.sent=true`，`data.prompt_length > prompt 长度`（说明追加了结束标记约定） |
| 3 | `fetch_output` | `win_key=trae`，`timeout_s=5` | `status=completed`，`data.text` 结尾含 `【Agent任务完成】` |
| 4 | `reload_window_rules` | `path` 留空 | `ok=true`，`data.clients` 三个键 |

### 异常路径验证（编排侧容错必测）

| 场景 | 做法 | 期望 |
| --- | --- | --- |
| 必填缺失 | `send_prompt` 只传 `win_key` | `INVALID_ARGUMENT`，`error.detail.fields` 有 `prompt` |
| 非法客户端 | `win_key=nope` | `INVALID_ARGUMENT`（Literal 校验拦截） |
| 规则文件坏 | `reload_window_rules` 传不存在的路径 | `RULES_INVALID`，`detail.path` 有值 |
| 注入发送失败 | `config.yaml` 里 `mock.inject_errors: {"trae:send": "SEND_FAILED"}` | `SEND_FAILED`，`ok=false` |
| 生成长等待 | `mock.generating_polls: 3` | 前 3 次 `fetch_output` 返回 `generating`，第 4 次 `completed` |
| 超时 | `mock.generating_polls: 999` + `timeout_s=1` | `status=timeout`，仍 `ok=true` |

## 6. 一键回归

```bat
.venv\Scripts\python -m pytest -q
```

覆盖：单元（39 项）→ 契约（双后端参数化）→ e2e（真起 stdio 子进程）。
全部在 Mock / Fake 驱动下运行，开发机无需任何 GUI 客户端。

## 7. 常见问题

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `No module named desktop_ai_orchestrator` | 未安装或未设 `PYTHONPATH` | `pip install -e .` |
| 端口被占用 | 上次进程未退出 | 换端口 `--port 8766`，或查 `netstat -ano \| findstr 8765` |
| Inspector 连 SSE 立即断开 | 用了 `/messages/` 而不是 `/sse` | 客户端连的是 `/sse`，`/messages/` 只给服务端回发消息用 |
| 客户端看到日志混进协议 | 用了 print / stdout handler | 检查是否自加了 `StreamHandler(sys.stdout)` |
| real 模式启动即报 `DEPENDENCY_MISSING` | 开发机没有 Windows 库 | 属预期；开发机用 `mode: mock` |
