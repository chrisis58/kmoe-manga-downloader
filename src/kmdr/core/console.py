"""
KMDR 用于管理控制台输出的模块。

提供信息、调试和日志记录功能，确保在交互式和非交互式环境中均能正确输出。
"""
from typing import Any
import sys
import io

from rich.console import Console
from rich.traceback import Traceback

_console_config = dict[str, Any](
    log_time_format="[%Y-%m-%d %H:%M:%S]",
)

try:
    utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='backslashreplace')
    _console_config['file'] = utf8_stdout
except io.UnsupportedOperation:
    pass

_console = Console(**_console_config)

_is_verbose = False

def _update_verbose_setting(value: bool):
    global _is_verbose
    _is_verbose = value

def info(*args, **kwargs):
    """
    在终端中输出信息
    
    会根据终端是否为交互式选择合适的输出方式。
    """
    if _console.is_interactive:
        _console.print(*args, **kwargs)
    else:
        _console.log(*args, **kwargs, _stack_offset=2)

def debug(*args, **kwargs):
    """
    在终端中输出调试信息
    
    `info` 的条件版本，仅当启用详细模式时才会输出。
    """
    if _is_verbose:
        if _console.is_interactive:
            _console.print("[dim]DEBUG:[/]", *args, **kwargs)
        else:
            _console.log("DEBUG:", *args, **kwargs, _stack_offset=2)

def log(*args, debug=False, **kwargs):
    """
    仅在非交互式终端中记录日志信息

    :warning: 仅在非交互式终端中输出日志信息，避免干扰交互式用户界面。
    """
    if _console.is_interactive:
        # 如果是交互式终端，则不记录日志
        return

    if debug and _is_verbose:
        # 仅在调试模式和启用详细模式时记录调试日志
        _console.log("DEBUG:", *args, **kwargs, _stack_offset=2)
    else:
        _console.log(*args, **kwargs, _stack_offset=2)

def exception(exception: Exception):
    _console.print((Traceback.from_exception(type(exception), exception, exception.__traceback__)))
