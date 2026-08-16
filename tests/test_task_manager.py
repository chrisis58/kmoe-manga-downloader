import asyncio
import importlib
import json
from argparse import Namespace

import kmdr.module  # noqa: F401
from kmdr.core.background import run_with_cancel_monitor
from kmdr.core.bases import TASK_MANAGER
from kmdr.module.task import TaskCanceller, TaskStatus


def test_task_manager_registry_dispatches_status_and_cancel():
    status = TASK_MANAGER.get(Namespace(task_command="status", task_id="task-1", wait=0))
    cancel = TASK_MANAGER.get(Namespace(task_command="cancel", task_id="task-1"))

    assert isinstance(status, TaskStatus)
    assert isinstance(cancel, TaskCanceller)


def test_task_parser_supports_namespace_and_progress_alias():
    from kmdr.core.defaults import argument_parser

    parser = argument_parser()
    task_args = parser.parse_args(["task", "status", "task-1", "--wait", "3"])
    legacy_args = parser.parse_args(["progress", "task-1"])

    assert (task_args.command, task_args.task_command, task_args.wait) == ("task", "status", 3)
    assert (legacy_args.command, legacy_args.task_command) == ("progress", "status")


def test_cancel_is_idempotent_for_completed_task(tmp_path, monkeypatch):
    task_canceller_module = importlib.import_module("kmdr.module.task.TaskCanceller")

    monkeypatch.setattr(task_canceller_module, "get_log_dir", lambda: str(tmp_path))
    log_path = tmp_path / "kmdr_done.log"
    log_path.write_text(json.dumps({"type": "result", "code": 0, "data": {"state": "completed"}}), encoding="utf-8")

    TaskCanceller("done").operate()

    assert not (tmp_path / "kmdr_done.cancel").exists()


def test_cancel_monitor_cancels_coroutine(tmp_path, monkeypatch):
    import kmdr.core.background as background

    cancel_path = tmp_path / "task.cancel"
    monkeypatch.setattr(background, "get_cancel_path", lambda task_id: str(cancel_path))

    async def work():
        await asyncio.sleep(30)

    async def exercise():
        runner = asyncio.create_task(run_with_cancel_monitor(work(), "task-1"))
        await asyncio.sleep(0.05)
        cancel_path.touch()
        await asyncio.wait_for(runner, timeout=2)

    asyncio.run(exercise())

    assert not cancel_path.exists()
