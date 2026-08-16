from kmdr.core.bases import TASK_MANAGER, TaskManager
from kmdr.core.task_query import query_task_status


@TASK_MANAGER.register(hasattrs=frozenset({"task_id"}), hasvalues={"task_command": "status"})
class TaskStatus(TaskManager):
    def __init__(self, task_id: str, wait: int = 0, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._task_id = task_id
        self._wait = wait

    def operate(self) -> None:
        query_task_status(self._task_id, self._wait)
