# 后端路由与接口（L2）

> 状态：P1 · 本轮只落 L2（`mode` 如何选后端、两后端共享哪些签名、错误码在谁那里产生）。
> 上一轮：L1 调用时序 `02-tool-call-sequence.md`。下一轮：L3 Real 后端内部结构（P2）。

## L2-1 分派路径

```
settings.mode
   │
   ├── "mock" ──► MockBackend
   │               ├ 窗口清单：来自 window_rules.json（静态）
   │               ├ 输出文本：脚本化 + 结束标记
   │               └ 可注入：latency / generating_polls / inject_errors
   │
   └── "real" ──► RealBackend(rules, driver=WindowsDriver, settings.real)
                   ├ 窗口枚举：EnumWindows + 标题/类名匹配
                   ├ 控件定位：有序 strategies 降级 + 重试
                   ├ 写入/发送：ValuePattern → SendKeys / Click 降级
                   └ 读取：轮询至出现结束标记或超时

构造期唯一会失败的点：real 模式在非 Windows 或缺依赖 → DEPENDENCY_MISSING（启动即失败，不带病运行）
```

## L2-2 两端共享的接口（`backends/base.py`）

| 方法 | 入参 | 返回 | 谁负责生成 correlation_id / elapsed_ms |
| --- | --- | --- | --- |
| `list_target_windows` | `include_unavailable` | `ListTargetWindowsData` | 工具层 |
| `send_prompt` | `win_key, prompt, append_marker` | `SendOutcome(data, turn_id)` | 工具层 |
| `fetch_output` | `win_key, timeout_s, since_last_send, max_chars` | `FetchOutputData` | 工具层 |
| `reload_window_rules` | `path` | `ReloadWindowRulesData` | 工具层 |

约定：
- 后端**只抛 `ToolError`**，不返回错误码字符串，不自己封装信封；
- 后端**不打印到 stdout**（stdio 协议通道）；
- `mock` 与 `real` 的方法签名必须逐字一致，契约测试对此参数化断言。

## L2-3 错误码产生位置

| 错误码 | 产生在 | 典型原因 |
| --- | --- | --- |
| `DEPENDENCY_MISSING` | `WindowsDriver.__init__` / `deps.require` | 非 Windows、缺 uiautomation/pywin32 |
| `RULES_INVALID` | `config/rules.py` / `config/loader.py` | JSON 语法、字段缺失、客户端键不匹配 |
| `WINDOW_NOT_FOUND` | `RealBackend._snapshot` / `WindowRules.get` | 客户端没启动、win_key 未配置 |
| `CONTROL_NOT_FOUND` | `RealBackend._locate_with_retry` | 控件路径随版本失效（需重新采集） |
| `SEND_FAILED` | `WindowsDriver.trigger_send` / `write_text` | 快捷键未生效、输入框只读 |
| `OUTPUT_TIMEOUT` | `WindowsDriver.read_text` | 输出区控件存在但读取抛错 |
| `INTERNAL_ERROR` | 工具层兜底 | 未预期异常 |

**不在后端产生**：`INVALID_ARGUMENT`（MCP 入参校验，工具层）、`OK`。

## L2-4 为什么工具层不做模式判断

反例（禁止）：

```python
if settings.mode == "real":
    ...真实实现...
else:
    ...模拟...
```

风险：逻辑分支散落在工具层，两模式行为必然漂移，契约测试无法覆盖。

正确做法：路由层一次性选出实例，工具层只面对 `Backend` 接口。新增第三种后端（如远程代理）
只需加一个实现 + 一行路由，工具层零改动。

## 下一层

- L3 Real 后端内部结构（窗口枚举 → 定位 → 写入 → 发送 → 轮询读取的调用栈与降级顺序）：P2 落 `04-real-backend-internals.md`
