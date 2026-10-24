# 工具契约（Tool Contract）v1.0.0 — 已冻结

> 状态：**已冻结（2026-10 阶段 1，tag 待打）**，对应 `src/desktop_ai_orchestrator/contracts/`。
> 冻结规则：工具名、字段名、错误码**只增不改不删**；破坏性变更必须升 MAJOR 并同步本文件与 `01`。
> 本文件与代码同源；冲突时以代码为准并立即回改本文（`04-dev-rules.md` §1）。

## 0. 公共信封

所有工具返回同一结构，`data` 为各工具专有部分：

```json
{
  "ok": true,
  "error_code": "OK",
  "message": "",
  "backend": "mock",
  "correlation_id": "c-6ad97c19-1f23-000002",
  "elapsed_ms": 0,
  "error": null,
  "data": { }
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ok` | bool | 成功标志。**判断成功只看这个**，不要解析 `message` |
| `error_code` | string | 见 §1；成功时恒为 `OK` |
| `message` | string | 人类可读说明；失败时是原因摘要 |
| `backend` | `"mock"` \| `"real"` | 数据来源，便于编排侧一眼分辨是否在真机上 |
| `correlation_id` | string | 单次调用唯一 ID，日志同 ID 可追溯 |
| `elapsed_ms` | int | 服务端耗时（不含网络） |
| `error` | object \| null | 失败时为 `{code, message, detail}`；成功时为 `null` |
| `data` | object \| null | 工具专有数据；**失败时恒为 `null`** |

## 1. 错误码（10 个，冻结）

| 错误码 | 触发条件 | 编排侧建议动作 |
| --- | --- | --- |
| `OK` | 成功 | 继续 |
| `INVALID_ARGUMENT` | 入参校验失败（缺字段/类型错/超长/非法 win_key） | 修参数，不要重试 |
| `WINDOW_NOT_FOUND` | 规则匹配不到窗口，或客户端没启动 | 提示用户启动客户端后重试 |
| `CONTROL_NOT_FOUND` | 窗口在，但输入框/发送/输出区所有策略都定位失败 | 需重新采集 `window_rules.json` |
| `SEND_FAILED` | 已写入但触发发送失败 | 可重试一次，仍失败则换客户端 |
| `OUTPUT_TIMEOUT` | **读输出区这个动作**本身失败 | 重试或重载规则 |
| `NOT_COMPLETED` | 保留码，一期未使用（常规等待用 `status`） | — |
| `RULES_INVALID` | `window_rules.json` 语法/结构/字段非法 | 修规则文件，`detail.errors` 有字段路径 |
| `DEPENDENCY_MISSING` | real 模式缺 Windows 库或非 Windows | 装 `requirements-real.txt`；开发机改 mock |
| `INTERNAL_ERROR` | 未预期异常兜底 | 报 bug，附 `correlation_id` |
| `MODE_MISMATCH` | 保留码，一期未使用 | — |

## 2. `list_target_windows`

入参：

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `include_unavailable` | bool | `false` | 是否返回未启动 / 控件未就绪的客户端 |

出参 `data`：

```json
{
  "windows": [
    {
      "win_key": "trae",
      "display_name": "Trae",
      "matched": true,
      "hwnd": 4097,
      "title": "[mock] Trae",
      "class_name": "Chrome_WidgetWin_1",
      "pid": 10001,
      "ready": true,
      "notes": ""
    }
  ]
}
```

| 字段 | 说明 |
| --- | --- |
| `matched` | 是否命中规则里的窗口 |
| `hwnd` | 真实句柄；mock 下为伪造值 |
| `ready` | 输入框与输出区都能定位（mock 恒 `true`） |
| `notes` | 不可用原因摘要，可直接展示给用户 |

- mock 恒返回三条且 `ready=true`；real 只返回可用的，除非 `include_unavailable=true`。
- 错误码：`RULES_INVALID`、`DEPENDENCY_MISSING`。

## 3. `send_prompt`

入参：

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `win_key` | `"trae"` \| `"qoder"` \| `"workbuddy"` | 必填 | 客户端标识 |
| `prompt` | string | 必填 | 正文，非空白，≤ 20000 字符 |
| `append_marker` | bool | `true` | 服务端自动在尾部追加结束标记约定 |

出参 `data`：

```json
{
  "win_key": "trae",
  "sent": true,
  "prompt_preview": "冒烟测试：输出一句话",
  "prompt_length": 39,
  "sent_at": "2026-10-22T10:59:15.606+08:00"
}
```

- `prompt_length` **大于** 入参 prompt 长度，说明结束标记约定已追加；`append_marker=false` 时二者相等。
- `prompt_preview` 只保留前 40 字（脱敏），不能用作回读正文。
- 错误码：`INVALID_ARGUMENT`、`WINDOW_NOT_FOUND`、`CONTROL_NOT_FOUND`、`SEND_FAILED`。

## 4. `fetch_output`

入参：

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `win_key` | 同上 | 必填 | 客户端标识 |
| `timeout_s` | float | `30` | 单次最长等待，(0, 300] |
| `since_last_send` | bool | `true` | 只取上次发送后的新增内容 |
| `max_chars` | int | `20000` | 返回文本上限，超出置 `truncated=true` |

出参 `data`：

```json
{
  "win_key": "trae",
  "status": "completed",
  "completed": true,
  "marker_found": true,
  "text": "……【Agent任务完成】",
  "text_length": 102,
  "truncated": false,
  "turn_id": "t-0001"
}
```

| `status` | `ok` | 含义 | 编排侧动作 |
| --- | --- | --- | --- |
| `completed` | true | 读到结束标记 | 取 `text` 进下一步 |
| `generating` | true | 有新增但无标记 | 继续轮询 |
| `timeout` | true | 到 `timeout_s` 仍无标记 | 再等或判断放弃 |
| `idle` | true | 无新增内容 | 继续轮询 |

**关键约定（ADR-005）**：四种状态全部 `ok=true`、`error_code=OK`。`timeout` 是"这次没等到"，不是任务失败。

- 错误码（真正的失败）：`INVALID_ARGUMENT`、`WINDOW_NOT_FOUND`、`CONTROL_NOT_FOUND`、`OUTPUT_TIMEOUT`。

## 5. `reload_window_rules`

入参：

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `path` | string \| null | `null` | 规则路径；null 则重载默认 `config/window_rules.json` |

出参 `data`：

```json
{
  "loaded": true,
  "path": "E:\\dd\\DesktopAI-Orchestrator\\config\\window_rules.json",
  "rules_version": "2025-01-01-template",
  "clients": ["trae", "qoder", "workbuddy"]
}
```

- 热重载不重启服务、不丢会话状态（mock 的轮次记录保留）。
- 错误码：`RULES_INVALID`（`detail.errors` 含字段路径，`detail.path` 含文件路径）。

## 6. `window_rules.json` 结构（v1.0）

```json
{
  "rules_version": "2025-01-01-template",
  "_comment": "以下划线开头的键是说明，加载时会被忽略",
  "clients": {
    "trae": {
      "display_name": "Trae",
      "title_keywords": ["Trae"],
      "class_name": "Chrome_WidgetWin_1",
      "client_version": "待采集",
      "collected_at": "待采集",
      "input":  [{ "type": "automation_id", "value": "chat-input", "notes": "示例值，必须替换" }],
      "send":   [{ "type": "accelerator", "value": "{ENTER}" }],
      "output": [{ "type": "automation_id", "value": "chat-list", "notes": "示例值，必须替换" }],
      "completion_marker": "【Agent任务完成】"
    },
    "qoder": { },
    "workbuddy": { }
  }
}
```

字段纪律：

| 字段 | 约束 |
| --- | --- |
| `clients` 键 | 必须**恰好**是 `trae` / `qoder` / `workbuddy`，多一个或少一个都报 `RULES_INVALID` |
| `title_keywords` | 至少 1 个，窗口标题包含任一即匹配 |
| `class_name` | 可选；Electron 通常为 `Chrome_WidgetWin_1` |
| `input` / `send` / `output` | 至少 1 条策略，**有序降级链**，按序尝试 |
| 未知字段 | 报错（防手误打错字段名被静默忽略） |
| `_` 开头的键 | 允许，加载时剔除（用于写注释） |

策略 `type` 取值（冻结）：

| type | value 含义 | 说明 |
| --- | --- | --- |
| `automation_id` | UIA AutomationId | 最稳，需工作机采集 |
| `control_type` | 控件类型（`edit` / `list` / `button`…） | 配合 `index` 取第 N 个 |
| `name` | UIA Name | 控件可见文本 |
| `class_name` | Win32 类名 | 粗粒度兜底 |
| `accelerator` | 快捷键（`{ENTER}` / `^{ENTER}`） | 仅 `send` 使用，不产生控件对象 |

## 7. 契约稳定性边界

冻结的是**结构**，不冻结的是：

- Mock 返回的文本内容（编排侧不得断言具体文案，只能断言 `status` / `marker_found`）；
- `hwnd` / `pid` 具体值；
- `elapsed_ms`、`correlation_id` 具体值；
- 日志格式（非契约）。

## 8. 待办（下一版，只增不改）

- [ ] `list_target_windows` 增加 `client_version` 回显，便于判断规则是否过期
- [ ] `fetch_output` 增加 `progress_hint`（如"文本长度在增长"），减少编排侧猜测
