import json
import os
import time
from pathlib import Path
from typing import Optional

from kmdr.core.background import get_log_dir
from kmdr.core.console import emit, in_toolcall_mode, info
from kmdr.core.error import KmdrError, TaskNotFoundError


def query_task_status(task_id: str, wait: int = 0):
    """读取并解析 NDJSON 日志，返回最新状态

    :param task_id: 任务 ID（时间戳格式，如 20260415_143000）
    :param wait: 阻塞等待时间（秒），任务完成则立即返回，默认 0（立即返回）
    """
    log_dir = get_log_dir()
    log_path = os.path.join(log_dir, f"kmdr_{task_id}.log")

    if not Path(log_path).exists():
        raise TaskNotFoundError(task_id)

    # 第一次读取日志
    volumes_status, final_result = parse_log_file(log_path)

    if final_result is not None:
        # 任务已完成，立即返回
        _handle_result(final_result, volumes_status)
        return

    # 任务进行中
    if wait <= 0:
        # 不等待，立即返回当前进度
        _handle_progress(volumes_status)
        return

    # 阻塞等待最多 wait 秒
    start_time = time.time()
    check_interval = 2  # 每 2 秒检查一次

    while time.time() - start_time < wait:
        time.sleep(check_interval)
        volumes_status, final_result = parse_log_file(log_path)

        if final_result is not None:
            # 任务完成，立即返回
            _handle_result(final_result, volumes_status)
            return

    # 等待超时，返回当前进度
    _handle_progress(volumes_status)


def parse_log_file(log_path: str) -> tuple[dict, Optional[dict]]:
    """解析日志文件，返回 volumes_status 和 final_result"""
    volumes_status = {}
    final_result = None

    try:
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line.startswith("{"):
                    continue

                try:
                    data = json.loads(line)
                    if data.get("type") == "result":
                        final_result = data
                    elif data.get("type") == "progress" and "volume" in data:
                        data.pop("type", None)
                        volumes_status[data.pop("volume")] = data
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        raise RuntimeError(f"读取日志异常: {str(e)}") from e

    return volumes_status, final_result


def _handle_result(final_result: dict, volumes_status: dict):
    """处理任务完成结果"""
    data = dict(final_result.get("data") or {})
    state = data.get("state", "completed" if final_result.get("code", 0) == 0 else "failed")
    if final_result.get("code", 0) == 0:
        if state == "cancelled":
            info("[yellow]下载任务已取消[/yellow]")
        else:
            info("[green]下载任务已完成[/green]")
    else:
        msg = final_result.get("msg", "未知错误")
        info(f"[red]下载任务失败: {msg}[/red]")
        raise KmdrError(f"下载任务失败 (code: {final_result.get('code', 'N/A')}): {msg}")

    if in_toolcall_mode():
        data.pop("state", None)
        emit(is_finished=True, state=state, volumes=volumes_status, **data)
        return

    if data:
        info(f"  漫画: {data.get('book', '未知')}")
        info(f"  总卷数: {data.get('total', 0)}")
        info(f"  成功: {data.get('completed', 0)}")
        info(f"  失败: {data.get('failed', 0)}")
        info(f"  跳过: {data.get('skipped', 0)}")
        if volumes_status:
            info("  各卷状态:")
            for vol_name, vol_status in volumes_status.items():
                status = vol_status.get("status", "unknown")
                if status == "completed":
                    info(f"    [green][OK] {vol_name}[/green]")
                elif status == "failed":
                    info(f"    [red][FAIL] {vol_name}[/red]")
                elif status == "skipped":
                    info(f"    [yellow][SKIP] {vol_name}[/yellow]")
                else:
                    info(f"    {vol_name} ({status})")


def _handle_progress(volumes_status: dict):
    """处理任务进行中进度"""
    if in_toolcall_mode():
        emit(is_finished=False, state="running", volumes=volumes_status)
        return

    info("[yellow]下载任务进行中[/yellow]")
    for vol_name, vol_status in volumes_status.items():
        status = vol_status.get("status", "unknown")
        percentage = vol_status.get("percentage", 0)
        if status == "completed":
            info(f"  [green][OK] {vol_name}[/green]")
        elif status == "downloading":
            info(f"  [blue]--> {vol_name} ({percentage:.1f}%)[/blue]")
        else:
            info(f"  {vol_name} ({status})")
