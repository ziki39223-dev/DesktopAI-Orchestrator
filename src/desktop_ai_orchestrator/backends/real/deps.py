"""Windows 依赖探测：统一管理 Real 专属库的延迟导入。

所有 ``import`` 都发生在函数内部，保证开发机（无这些库）仍能以 mock 模式启动。
"""

from __future__ import annotations

from types import ModuleType

from ...contracts.errors import ErrorCode, ToolError

#: 依赖名 → pip 包名，用于错误提示。
DEPENDENCY_HINTS: dict[str, str] = {
    "uiautomation": "uiautomation",
    "comtypes": "comtypes",
    "win32gui": "pywin32",
    "windows_capture": "windows-capture",
}


def require(module_name: str) -> ModuleType:
    """导入 Windows 专属模块，失败时抛 ``DEPENDENCY_MISSING``。"""
    try:
        return __import__(module_name)
    except ImportError as exc:
        hint = DEPENDENCY_HINTS.get(module_name, module_name)
        raise ToolError(
            ErrorCode.DEPENDENCY_MISSING,
            f"real 模式缺少依赖：{module_name}（pip install {hint}）",
            detail={"module": module_name, "pip": hint},
        ) from exc


def probe() -> dict[str, bool]:
    """探测各依赖是否可用，供启动自检与调试使用。"""
    result: dict[str, bool] = {}
    for name in DEPENDENCY_HINTS:
        try:
            __import__(name)
        except ImportError:
            result[name] = False
        else:
            result[name] = True
    return result


def is_windows() -> bool:
    import sys

    return sys.platform == "win32"
