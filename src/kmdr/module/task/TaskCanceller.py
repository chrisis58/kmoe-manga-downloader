import os
from pathlib import Path

from kmdr.core.background import get_cancel_path, get_log_dir
from kmdr.core.bases import TASK_MANAGER, TaskManager
from kmdr.core.console import emit, info
from kmdr.core.error import TaskNotFoundError

from .query import parse_log_file


@TASK_MANAGER.register(hasattrs=frozenset({"task_id"}), hasvalues={"task_command": "cancel"})
class TaskCanceller(TaskManager):
    def __init__(self, task_id: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._task_id = task_id

    def operate(self) -> None:
        log_path = Path(get_log_dir()) / f"kmdr_{self._task_id}.log"
        if not log_path.exists():
            raise TaskNotFoundError(self._task_id)

        _, final_result = parse_log_file(str(log_path))
        if final_result is not None:
            data = final_result.get("data") or {}
            state = data.get("state", "completed" if final_result.get("code", 0) == 0 else "failed")
            info(f"任务已经结束: {state}")
            emit(task_id=self._task_id, state=state)
            return

        cancel_path = get_cancel_path(self._task_id)
        fd = os.open(cancel_path, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(fd)
        info("[yellow]已发送取消请求[/yellow]")
        emit(task_id=self._task_id, state="cancelling")
