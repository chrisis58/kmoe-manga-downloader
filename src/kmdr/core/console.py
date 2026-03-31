"""
KMDR 用于管理控制台输出的模块。

提供信息、调试和日志记录功能，确保在交互式和非交互式环境中均能正确输出。
"""

import io
import sys
from enum import Enum
from typing import Any

from rich.console import Console
from rich.traceback import Traceback

from .patch import apply_status_patch

_console_config = dict[str, Any](
    log_time_format="[%Y-%m-%d %H:%M:%S]",
)

try:
    utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")
    _console_config["file"] = utf8_stdout
except io.UnsupportedOperation:
    pass

_console = Console(**_console_config)
apply_status_patch(_console)  # Monkey patch

_is_verbose = False


class OutputMode(str, Enum):
    INTERACTIVE = "interactive"
    LOG = "log"
    TOOLCALL = "toolcall"


_current_mode: OutputMode = OutputMode.INTERACTIVE


def in_toolcall_mode() -> bool:
    """判断当前是否为工具调用模式，不显示富文本"""
    if _current_mode == OutputMode.TOOLCALL:
        return True
    return "toolcall" in sys.argv


def _set_output_mode(mode: OutputMode):
    global _current_mode
    _current_mode = mode
    if in_toolcall_mode():
        _console.quiet = True

        import atexit

        atexit.register(_flush_emit)


def _update_verbose_setting(value: bool):
    global _is_verbose
    _is_verbose = value


def is_interactive() -> bool:
    """判断当前是否为交互式终端"""
    # 默认兜底或显式指定 interactive 时，都需检查终端环境
    if _current_mode == OutputMode.INTERACTIVE:
        return _console.is_interactive
    return False


def info(*args, **kwargs):
    """
    在终端中输出信息

    会根据终端是否为交互式选择合适的输出方式。
    """
    if in_toolcall_mode():
        # 工具调用模式不渲染富文本
        return

    if is_interactive():
        _console.print(*args, **kwargs)
    else:
        _console.log(*args, **kwargs, _stack_offset=2)


def debug(*args, **kwargs):
    """
    在终端中输出调试信息

    `info` 的条件版本，仅当启用详细模式时才会输出。
    """
    if in_toolcall_mode():
        # 工具调用模式不支持显示调试信息
        return

    if _is_verbose:
        if is_interactive():
            _console.print("[dim]DEBUG:[/]", *args, **kwargs)
        else:
            _console.log("DEBUG:", *args, **kwargs, _stack_offset=2)


def log(*args, debug=False, **kwargs):
    """
    仅在非交互式终端中记录日志信息

    :warning: 仅在非交互式终端中输出日志信息，避免干扰交互式用户界面。
    """
    if in_toolcall_mode() or is_interactive():
        # 如果是交互式终端或工具调用模式，则不记录日志
        return

    if debug and _is_verbose:
        # 仅在调试模式和启用详细模式时记录调试日志
        _console.log("DEBUG:", *args, **kwargs, _stack_offset=2)
    else:
        _console.log(*args, **kwargs, _stack_offset=2)


_emit_payload = None


def emit(*args, **kwargs):
    """
    专门用于在工具调用模式下，向下游暂存最终的规整数据。
    该函数支持多次调用，但只有生命周期中最后一次调用时传入的数据才会在程序退出时被真正输出。
    """
    if not in_toolcall_mode():
        # 非工具调用模式下，不额外输出这段纯数据
        return

    global _emit_payload
    _emit_payload = (args, kwargs)


def _flush_emit():
    if _emit_payload is not None:
        was_quiet = _console.quiet
        _console.quiet = False
        try:
            args, kwargs = _emit_payload

            import json

            from .encoder import SafeJSONEncoder

            payload = kwargs if kwargs else args[0]
            response = {}

            if isinstance(payload, Exception):
                response["code"] = getattr(payload, "code", 50)
                response["msg"] = str(payload) or payload.__class__.__name__
                response["data"] = None
            else:
                response["code"] = 0
                response["msg"] = "success"
                response["data"] = payload

            output_str = json.dumps(response, cls=SafeJSONEncoder, ensure_ascii=False, indent=2)
            _console.print(output_str, markup=False, highlight=False)
        finally:
            _console.quiet = was_quiet


def exception(exception: Exception):
    _console.print(Traceback.from_exception(type(exception), exception, exception.__traceback__))
