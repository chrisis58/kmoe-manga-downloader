from enum import Enum
import asyncio

from rich.progress import Progress, TaskID


class STATUS(Enum):
    WAITING='[blue]等待中[/blue]'
    RETRYING='[yellow]重试中[/yellow]'
    DOWNLOADING='[cyan]下载中[/cyan]'
    MERGING='[magenta]合并中[/magenta]'
    COMPLETED='[green]完成[/green]'
    PARTIALLY_FAILED='[red]分片失败[/red]'
    FAILED='[red]失败[/red]'

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
        }
        return order_mapping[self]
    
    def __lt__(self, other):
        if not isinstance(other, STATUS):
            return NotImplemented
        return self.order < other.order


class StateManager:

    def __init__(self, progress: Progress, task_id: TaskID):
        self._part_states: dict[int, STATUS] = {}
        self._progress = progress
        self._task_id = task_id
        self._current_status = STATUS.WAITING

        self._lock = asyncio.Lock()

    PARENT_ID: int = -1

    def advance(self, advance: int):
        self._progress.update(self._task_id, advance=advance)

    def _update_status(self):
        if not self._part_states:
            return
        
        highest_status = max(self._part_states.values())
        if highest_status != self._current_status:
            self._current_status = highest_status
            self._progress.update(self._task_id, status=highest_status.value, refresh=True)

    async def request_status_update(self, part_id: int, status: STATUS):
        async with self._lock:
            self._part_states[part_id] = status
            self._update_status()
