#!/usr/bin/env python3
"""
Kmdr Companion — Native Messaging Host

Bridges the browser extension to kmdr CLI via stdin/stdout JSON.
Supports local execution and SSH remote execution.
"""

import json
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

# --- Native Messaging protocol ---


def read_message() -> dict | None:
    """Read a length-prefixed JSON message from stdin."""
    raw_len = sys.stdin.buffer.read(4)
    if not raw_len:
        return None
    msg_len = struct.unpack("@I", raw_len)[0]
    raw_data = sys.stdin.buffer.read(msg_len)
    return json.loads(raw_data.decode("utf-8"))


def send_message(data: dict) -> None:
    """Write a length-prefixed JSON message to stdout."""
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("@I", len(raw)))
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()


# --- Command builders ---


def build_kmdr_command(action: str, params: dict) -> list[str]:
    """Build a kmdr command line from action + params."""
    cmd = ["kmdr", "--mode", "toolcall"]

    if action == "download":
        cmd.append("download")
        cmd.extend(["-l", params["book_url"]])
        cmd.extend(["--vol-ids", params["vol_ids"]])
        cmd.append("--background")
        if params.get("format"):
            cmd.extend(["-f", params["format"]])
        if params.get("dest"):
            cmd.extend(["-d", params["dest"]])
        if params.get("vol_type"):
            cmd.extend(["-t", params["vol_type"]])

    elif action == "status":
        cmd.append("status")

    elif action == "progress":
        cmd.append("progress")
        cmd.append(params["task_id"])
        cmd.extend(["--wait", str(params.get("wait", 0))])

    else:
        raise ValueError(f"Unknown action: {action}")

    return cmd


def run_local(command: list[str], timeout: int = 30) -> dict:
    """Run kmdr locally via subprocess."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = result.stdout.strip()

        if result.returncode != 0:
            return {
                "code": result.returncode,
                "msg": result.stderr.strip() or f"kmdr exited with code {result.returncode}",
                "action": command[2],  # subcommand name
                "data": None,
            }

        # Parse kmdr's structured output (last NDJSON line with "type":"result")
        for line in reversed(stdout.splitlines()):
            if not line.startswith("{"):
                continue
            try:
                parsed = json.loads(line)
                if parsed.get("type") == "result":
                    return {
                        "code": parsed.get("code", 0),
                        "msg": parsed.get("msg", "success"),
                        "action": command[2],
                        "data": parsed.get("data"),
                    }
            except json.JSONDecodeError:
                continue

        # Fallback: return raw output
        return {
            "code": 0,
            "msg": "success",
            "action": command[2],
            "data": {"raw": stdout} if stdout else None,
        }

    except subprocess.TimeoutExpired:
        return {
            "code": 100,
            "msg": "命令执行超时",
            "action": command[2],
            "data": None,
        }
    except FileNotFoundError:
        return {
            "code": 101,
            "msg": "kmdr 未找到，请确认已安装 kmoe-manga-downloader",
            "action": command[2],
            "data": None,
        }


def run_ssh(ssh_config: dict, command: list[str], timeout: int = 30) -> dict:
    """Run kmdr remotely via SSH."""
    host = ssh_config.get("host", "")
    user = ssh_config.get("user", "")
    port = ssh_config.get("port", 22)

    if not host:
        return {"code": 102, "msg": "SSH 目标主机未配置", "action": command[2], "data": None}

    target = f"{user}@{host}" if user else host
    quoted_cmd = " ".join(command)  # kmdr --mode toolcall download ...
    ssh_cmd = [
        "ssh",
        "-p", str(port),
        "-o", "ConnectTimeout=10",
        "-o", "BatchMode=yes",
        target,
        quoted_cmd,
    ]

    try:
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = result.stdout.strip()

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "Permission denied" in stderr:
                hint = " (请确认 SSH key 已配置)"
            elif "Could not resolve" in stderr or "Name or service not known" in stderr:
                hint = " (无法解析主机名)"
            elif "Connection refused" in stderr:
                hint = " (连接被拒绝，请检查目标主机和端口)"
            elif "Connection timed out" in stderr:
                hint = " (连接超时)"
            else:
                hint = ""
            return {
                "code": result.returncode,
                "msg": f"SSH 连接失败: {stderr}{hint}" if stderr else f"SSH 退出码 {result.returncode}",
                "action": command[2],
                "data": None,
            }

        # Parse kmdr output (same as local)
        for line in reversed(stdout.splitlines()):
            if not line.startswith("{"):
                continue
            try:
                parsed = json.loads(line)
                if parsed.get("type") == "result":
                    return {
                        "code": parsed.get("code", 0),
                        "msg": parsed.get("msg", "success"),
                        "action": command[2],
                        "data": parsed.get("data"),
                    }
            except json.JSONDecodeError:
                continue

        return {
            "code": 0,
            "msg": "success",
            "action": command[2],
            "data": {"raw": stdout} if stdout else None,
        }

    except subprocess.TimeoutExpired:
        return {"code": 100, "msg": "SSH 命令执行超时", "action": command[2], "data": None}


# --- Main loop ---


def main() -> None:
    while True:
        request = read_message()
        if request is None:
            break

        action = request.get("action", "")
        params = request.get("params", {})
        target = request.get("target", "local")

        try:
            command = build_kmdr_command(action, params)
        except ValueError as e:
            send_message({"code": 103, "msg": str(e), "action": action, "data": None})
            continue

        if target == "local":
            result = run_local(command)
        elif isinstance(target, dict) and target.get("host"):
            result = run_ssh(target, command)
        else:
            result = {"code": 104, "msg": "无效的连接目标配置", "action": action, "data": None}

        send_message(result)


if __name__ == "__main__":
    main()
