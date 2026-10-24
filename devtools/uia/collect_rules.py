"""UIA 控件采集辅助（只读探测，供工作机使用）。

作用：把某个窗口的 UIA 树打印出来，并把候选控件转成可直接粘进
``window_rules.json`` 的 strategy 片段。**只读**——不写入、不点击、不发送。

用法（工作机）：
    python devtools/uia/collect_rules.py list
    python devtools/uia/collect_rules.py dump --title Trae --depth 6
    python devtools/uia/collect_rules.py suggest --title Trae
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

try:
    import uiautomation as auto
except ImportError:  # 非工作机 / 未装依赖
    auto = None  # type: ignore[assignment]


def _require() -> Any:
    if auto is None:
        print(
            "[错误] 未安装 uiautomation：pip install -r requirements-real.txt\n"
            "       本脚本只能在已安装 Trae / Qoder / WorkBuddy 的 Windows 工作机上使用。",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return auto


def cmd_list() -> int:
    """列出所有可见顶层窗口，帮助确认标题关键词与类名。"""
    gui = __import__("win32gui")
    rows: list[tuple[int, str, str]] = []

    def _collect(hwnd: int, _extra: Any) -> bool:
        if gui.IsWindowVisible(hwnd):
            title = gui.GetWindowText(hwnd)
            if title:
                rows.append((hwnd, title, gui.GetClassName(hwnd)))
        return True

    gui.EnumWindows(_collect, None)
    for hwnd, title, class_name in rows:
        print(f"0x{hwnd:08X}  class={class_name:<24}  title={title}")
    print(f"\n共 {len(rows)} 个可见窗口")
    return 0


def cmd_dump(title: str, depth: int, max_nodes: int) -> int:
    """打印指定标题窗口的 UIA 树（只读）。"""
    auto_mod = _require()
    window = auto_mod.WindowControl(searchDepth=2, SubName=title)
    if not window.Exists(2, 0.5):
        print(f"[错误] 未找到标题包含 {title!r} 的窗口", file=sys.stderr)
        return 1

    print(f"窗口：{window.Name!r}  ClassName={window.ClassName!r}  "
          f"AutomationId={window.AutomationId!r}")

    printed = 0

    def _walk(control: Any, level: int) -> None:
        nonlocal printed
        if level > depth or printed >= max_nodes:
            return
        printed += 1
        indent = "  " * level
        print(
            f"{indent}- {control.ControlTypeName:<18} "
            f"Name={control.Name[:40]!r:<44} "
            f"AutoId={control.AutomationId!r:<20} "
            f"Class={control.ClassName!r}"
        )
        for child in control.GetChildren():
            _walk(child, level + 1)

    _walk(window, 0)
    print(f"\n共打印 {printed} 个节点（depth={depth}）")
    return 0


def cmd_suggest(title: str) -> int:
    """把 Edit / Button / List 类控件转成可用的 strategy 片段。"""
    auto_mod = _require()
    window = auto_mod.WindowControl(searchDepth=2, SubName=title)
    if not window.Exists(2, 0.5):
        print(f"[错误] 未找到标题包含 {title!r} 的窗口", file=sys.stderr)
        return 1

    buckets: dict[str, list[dict[str, Any]]] = {"input": [], "send": [], "output": []}

    def _walk(control: Any, level: int) -> None:
        if level > 10:
            return
        type_name = control.ControlTypeName
        candidates: list[dict[str, Any]] = []
        if control.AutomationId:
            candidates.append({"type": "automation_id", "value": control.AutomationId})
        if control.Name:
            candidates.append({"type": "name", "value": control.Name})
        candidates.append({"type": "control_type", "value": type_name.removesuffix("Control").lower()})

        if type_name in {"EditControl", "DocumentControl"}:
            buckets["input"].extend(candidates[:2])
        elif type_name in {"ButtonControl"} and control.Name:
            buckets["send"].extend(candidates[:2])
        elif type_name in {"ListControl", "PaneControl"} and control.AutomationId:
            buckets["output"].extend(candidates[:1])

        for child in control.GetChildren():
            _walk(child, level + 1)

    _walk(window, 0)

    print("// 复制到 window_rules.json 对应客户端下，按稳定性排序、删掉不适用的条目")
    print(json.dumps(buckets, ensure_ascii=False, indent=2))
    print(
        "\n// 注意：以上仅为候选，需人工确认哪一个真正对应聊天输入框 / 输出区。\n"
        "// 确认方法：get_value 前后对比 —— 发送一条消息，看哪个控件文本变长。"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="UIA 控件采集辅助（只读）")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="列出可见顶层窗口")

    dump = sub.add_parser("dump", help="打印窗口 UIA 树")
    dump.add_argument("--title", required=True, help="窗口标题关键词")
    dump.add_argument("--depth", type=int, default=5)
    dump.add_argument("--max-nodes", type=int, default=400)

    suggest = sub.add_parser("suggest", help="生成 strategy 候选片段")
    suggest.add_argument("--title", required=True, help="窗口标题关键词")

    args = parser.parse_args()
    if args.command == "list":
        return cmd_list()
    if args.command == "dump":
        return cmd_dump(args.title, args.depth, args.max_nodes)
    return cmd_suggest(args.title)


if __name__ == "__main__":
    raise SystemExit(main())
