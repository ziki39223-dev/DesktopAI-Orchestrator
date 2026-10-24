# 一次工具调用的时序（L1）

> 状态：P1 · 本轮只落 L1。L2（路由分派与后端接口）下一轮补，见 `00-doc-map.md` §2。
> 关注点：`send_prompt` 一次 + `fetch_output` 多轮轮询，以及"未完成不是错误"如何体现。

## L1-1 正常闭环（无失败）

```
编排器                 MCP 服务(tools)        后端(mock/real)         客户端窗口
  │                          │                       │                    │
  │ list_target_windows ────►│ 校验入参               │                    │
  │                          │──── list ────────────►│ 枚举/读规则         │
  │◄─── {ok, data.windows} ──│◄───────────────────────│                    │
  │                          │                       │                    │
  │ send_prompt(win_key,p) ─►│ 追加结束标记约定       │                    │
  │                          │──── send ────────────►│ 定位输入框→写入→发送│
  │◄─── {ok, data.turn_id} ──│◄───────────────────────│                    │
  │                          │                       │                    │
  │ fetch_output(win_key) ──►│                       │ 读输出区            │
  │                          │──── fetch ───────────►│                    │
  │◄── status=generating ────│◄───────────────────────│                    │
  │        （继续轮询）       │                       │                    │
  │ fetch_output(win_key) ──►│                       │                    │
  │◄── status=completed ─────│◄───────────────────────│ 文本含结束标记      │
  │                          │                       │                    │
  │ ── 取 text 进入下一步 ──  │                       │                    │
```

## L1-2 状态机（fetch_output 的四种返回）

```
            ┌────────────── 每次调用 ──────────────┐
            ▼                                       │
  [idle] ── 无新增内容 ──────────► idle ────────────┤
     │                                              │
     ├── 有新增但无标记 ────────► generating ────────┤
     │                                              │
     ├── 出现结束标记 ──────────► completed（终态）  │
     │                                              │
     └── 到 timeout_s ──────────► timeout ──────────┘
                                    │
                                    └─► 由编排器决定：继续等 / 判失败 / 换客户端
```

关键约定：
- 四种状态**全部 `ok=true`**，`error_code=OK`。编排器只看 `status`，不靠抓异常。
- `timeout` 是"本次调用没等到"，不是任务失败，重试同一工具即可。
- 真正的硬失败只有：`WINDOW_NOT_FOUND` / `CONTROL_NOT_FOUND` / `OUTPUT_TIMEOUT` / `SEND_FAILED`。

## L1-3 失败分支（一次调用内）

```
tools 层
  ├─ 入参校验失败 ─────────► INVALID_ARGUMENT（data=None, error.detail.fields）
  ├─ 后端抛 ToolError ─────► 对应错误码（data=None, error.detail）
  └─ 后端抛其它异常 ───────► INTERNAL_ERROR（兜底，日志带堆栈）

任何分支都不向 MCP 层抛裸异常 → 编排器永远拿到同一套信封结构。
```

## 下一层

- L2 路由层与后端接口：`mode` 如何选后端、两后端共享哪些方法签名 → 下一轮写 `03-backend-routing.md`
