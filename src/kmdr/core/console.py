import sys
import io

from rich.console import Console
from rich.traceback import Traceback

from kmdr.core.defaults import is_verbose

try:
    utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='backslashreplace')
    _console = Console(file=utf8_stdout)
except io.UnsupportedOperation:
    _console = Console()

def info(*args, **kwargs):
    if _console.is_interactive:
        _console.print(*args, **kwargs)
    else:
        _console.log(*args, **kwargs, _stack_offset=2)

def debug(*args, **kwargs):
    if is_verbose():
        if _console.is_interactive:
            _console.print("[dim]DEBUG:[/]", *args, **kwargs)
        else:
            _console.log("DEBUG:", *args, **kwargs, _stack_offset=2)

def exception(exception: Exception):
    _console.print((Traceback.from_exception(type(exception), exception, exception.__traceback__)))
