import asyncio
import os
import subprocess
import sys
import tempfile
from datetime import datetime


def get_log_dir() -> str:
    log_dir = os.path.join(tempfile.gettempdir(), "kmdr")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def create_log_file() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    log_dir = get_log_dir()
    log_path = os.path.join(log_dir, f"kmdr_{timestamp}.log")
    return log_path


def spawn_background_process(args: list[str], log_file: str, task_id: str) -> int:
    filtered_args = []
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg in ("-b", "--background"):
            continue
        if arg.startswith("--mode="):
            continue
        if arg == "--mode":
            skip_next = True
            continue
        filtered_args.append(arg)

    filtered_args.insert(0, "--mode")
    filtered_args.insert(1, "toolcall")

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.DETACHED_PROCESS

    with open(log_file, "w", encoding="utf-8") as log_f:
        env = os.environ.copy()
        env["KMDR_TASK_ID"] = task_id
        process = subprocess.Popen(
            [sys.executable, "-m", "kmdr"] + filtered_args,
            stdout=log_f,
            stderr=log_f,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
            env=env,
        )

    return process.pid


def start_background(args: list[str]) -> tuple[str, int]:
    log_file = create_log_file()
    task_id = os.path.basename(log_file).replace("kmdr_", "").replace(".log", "")
    pid = spawn_background_process(args, log_file, task_id)
    return task_id, pid


def get_cancel_path(task_id: str) -> str:
    return os.path.join(get_log_dir(), f"kmdr_{task_id}.cancel")


async def run_with_cancel_monitor(coro, task_id: str) -> None:
    """运行后台任务，并在收到控制文件请求时协作式取消。"""
    from .console import emit

    cancel_path = get_cancel_path(task_id)
    try:
        os.remove(cancel_path)
    except FileNotFoundError:
        pass

    main_task = asyncio.create_task(coro)
    try:
        while not main_task.done():
            if os.path.exists(cancel_path):
                main_task.cancel()
                try:
                    await main_task
                except asyncio.CancelledError:
                    pass
                emit(task_id=task_id, state="cancelled")
                return
            await asyncio.sleep(0.5)
        await main_task
    finally:
        try:
            os.remove(cancel_path)
        except FileNotFoundError:
            pass
