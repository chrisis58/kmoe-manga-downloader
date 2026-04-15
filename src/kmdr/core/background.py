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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = get_log_dir()
    log_path = os.path.join(log_dir, f"kmdr_{timestamp}.log")
    return log_path


def spawn_background_process(args: list[str], log_file: str) -> int:
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
        creationflags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS

    with open(log_file, "w", encoding="utf-8") as log_f:
        process = subprocess.Popen(
            [sys.executable, "-m", "kmdr"] + filtered_args,
            stdout=log_f,
            stderr=log_f,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
        )

    return process.pid


def start_background(args: list[str]) -> tuple[str, int]:
    log_file = create_log_file()
    pid = spawn_background_process(args, log_file)
    return log_file, pid
