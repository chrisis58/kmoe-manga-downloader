import json
import os
import tempfile
from pathlib import Path

from .console import emit, in_toolcall_mode, info


def resolve_log_path(arg: str) -> str:
    """解析参数为日志文件路径

    支持两种形式:
    - 完整路径: 直接使用
    - task_id (时间戳): 自动拼接临时目录路径
    """
    if os.path.sep in arg or (os.path.altsep and os.path.altsep in arg):
        return arg

    log_dir = os.path.join(tempfile.gettempdir(), "kmdr")
    return os.path.join(log_dir, f"kmdr_{arg}.log")


def query_task_status(log_path: str) -> dict:
    """读取并解析 NDJSON 日志，按卷分组重建最新状态"""
    log_path = resolve_log_path(log_path)

    if not Path(log_path).exists():
        result = {"type": "error", "code": 404, "msg": f"未找到日志文件: {log_path}"}
        emit(type="result", code=404, msg=f"未找到日志文件: {log_path}")
        if not in_toolcall_mode():
            info(f"[red]错误: 未找到日志文件 {log_path}[/red]")
        return result

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
                        volumes_status[data["volume"]] = data
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        result = {"type": "error", "code": 500, "msg": f"读取日志异常: {str(e)}"}
        emit(result)
        if not in_toolcall_mode():
            info(f"[red]错误: 读取日志异常 {str(e)}[/red]")
        return result

    result = {
        "type": "task_status",
        "is_finished": final_result is not None,
        "volumes": volumes_status,
        "final_result": final_result,
    }
    emit(result)
    if not in_toolcall_mode():
        _print_status_summary(result)
    return result


def _print_status_summary(result: dict):
    if result.get("is_finished"):
        final_result = result.get("final_result")
        if final_result and final_result.get("code", 0) == 0:
            info("[green]下载任务已完成[/green]")
        else:
            msg = final_result.get("msg", "未知错误") if final_result else "未知错误"
            info(f"[red]下载任务失败: {msg}[/red]")
    else:
        info("[yellow]下载任务进行中[/yellow]")

    volumes = result.get("volumes", {})
    if volumes:
        for vol_name, vol_status in volumes.items():
            status = vol_status.get("status", "unknown")
            progress = vol_status.get("progress", 0)
            if status == "completed":
                info(f"  [green]✓ {vol_name}[/green]")
            elif status == "downloading":
                info(f"  [blue]→ {vol_name} ({progress:.1f}%)[/blue]")
            else:
                info(f"  {vol_name} ({status})")
