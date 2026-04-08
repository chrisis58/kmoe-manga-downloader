import asyncio
import subprocess
from enum import Enum
from typing import Callable, Optional

from rich.progress import Progress, TaskID

from kmdr.core.console import debug, emit_progress, in_toolcall_mode
from kmdr.core.structure import BookInfo, VolInfo


class DownloadTracker:
    def __init__(self, total: int):
        self._total = total
        self._completed = 0
        self._failed = 0
        self._skipped = 0

    @property
    def total(self) -> int:
        return self._total

    @property
    def completed(self) -> int:
        return self._completed

    @property
    def failed(self) -> int:
        return self._failed

    @property
    def skipped(self) -> int:
        return self._skipped

    def __call__(self, status: str, **kwargs):
        if not in_toolcall_mode():
            return

        if status == "completed":
            self._completed += 1
        elif status == "failed":
            self._failed += 1
        elif status == "skipped":
            self._skipped += 1

        emit_progress(status=status, **kwargs)


def construct_callback(callback: Optional[str]) -> Optional[Callable]:
    if callback is None or not isinstance(callback, str) or not callback.strip():
        return None

    def _callback(book: BookInfo, volume: VolInfo) -> int:
        nonlocal callback

        assert callback, "Callback script cannot be empty"
        formatted_callback = callback.strip().format(b=book, v=volume)

        return subprocess.run(formatted_callback, shell=True, check=True).returncode

    return _callback


class STATUS(Enum):
    WAITING = "[blue]等待中[/blue]"
    RETRYING = "[yellow]重试中[/yellow]"
    DOWNLOADING = "[cyan]下载中[/cyan]"
    MERGING = "[magenta]合并中[/magenta]"
    COMPLETED = "[green]完成[/green]"
    PARTIALLY_FAILED = "[red]分片失败[/red]"
    FAILED = "[red]失败[/red]"
    CANCELLED = "[yellow]已取消[/yellow]"

    @property
    def order(self) -> int:
        order_mapping = {
            STATUS.WAITING: 1,
            STATUS.RETRYING: 2,
            STATUS.DOWNLOADING: 3,
            STATUS.MERGING: 4,
            STATUS.COMPLETED: 5,
            STATUS.PARTIALLY_FAILED: 6,
            STATUS.FAILED: 7,
            STATUS.CANCELLED: 8,
        }
        return order_mapping[self]

    def __lt__(self, other):
        if not isinstance(other, STATUS):
            return NotImplemented
        return self.order < other.order


class StateManager:
    def __init__(
        self,
        progress: Progress,
        task_id: TaskID,
        progress_callback: Optional[Callable[..., None]] = None,
        emit_interval: int = 10 * 1024 * 1024,
    ):
        self._part_states: dict[int, STATUS] = {}
        self._progress = progress
        self._task_id = task_id
        self._current_status = STATUS.WAITING
        self._progress_callback = progress_callback
        self._emit_interval = emit_interval
        self._last_emit_size = 0

        self._lock = asyncio.Lock()

    PARENT_ID: int = -1

    def advance(self, advance: int):
        self._progress.update(self._task_id, advance=advance)
        if self._progress_callback:
            task = self._progress.tasks[self._task_id]
            total = task.total
            if total is not None and total > 0:
                if task.completed - self._last_emit_size > self._emit_interval:
                    self._progress_callback(status="downloading", percentage=round(task.completed / total * 100, 1))
                    self._last_emit_size = task.completed

    def _update_status(self):
        if not self._part_states:
            return

        highest_status = max(self._part_states.values())
        if highest_status != self._current_status:
            self._current_status = highest_status
            self._progress.update(self._task_id, status=highest_status.value)

    async def pop_part(self, part_id: int):
        """
        下载完成后移除分片状态记录，不再参与状态计算

        :note: 为避免状态闪烁，调用后不会更新状态
        """
        async with self._lock:
            if part_id in self._part_states:
                self._part_states.pop(part_id)

    async def request_status_update(self, part_id: int, status: STATUS):
        async with self._lock:
            debug("分片", part_id, "请求状态更新为", status)
            self._part_states[part_id] = status
            self._update_status()

