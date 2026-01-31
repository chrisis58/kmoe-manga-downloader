from rich.status import Status
from contextlib import contextmanager


class _StackedStatusManager:
    def __init__(self, console):
        self.console = console
        self._stack = []
        self._finished = set()
        self._live_status = None

    def _clean_stack_top(self):
        while self._stack:
            token, _ = self._stack[-1]
            if token in self._finished:
                self._stack.pop()
                self._finished.remove(token)
            else:
                break

    def _refresh(self):
        self._clean_stack_top()

        if not self._stack:
            self._finished.clear()
            if self._live_status:
                self._live_status.stop()
                self._live_status = None
        else:
            _, text = self._stack[-1]
            if self._live_status is None:
                self._live_status = Status(text, console=self.console)
                self._live_status.start()
            else:
                self._live_status.update(text)

    @contextmanager
    def status(self, text):
        token = object()

        self._stack.append((token, text))
        self._refresh()

        try:
            yield
        finally:
            self._finished.add(token)
            self._refresh()


def apply_status_patch(console_instance):
    """
    为 Console.status() 提供可嵌套支持，避免在 asyncio 并发场景下触发 LiveError。

    前提与限制：
    - 仅适用于单线程 asyncio 应用
    - 所有协程必须复用同一个 Console 实例
    """
    manager = _StackedStatusManager(console_instance)
    console_instance.status = manager.status
