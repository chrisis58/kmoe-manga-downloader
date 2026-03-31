import argparse
import json
import sys
from contextlib import contextmanager

from rich.status import Status


class _StackedStatusManager:
    def __init__(self, console):
        self.console = console
        self._stack = []
        self._finished = set()
        self._live_status = None

    def _clean_stack_top(self):
        while self._stack:
            token, _ = self._stack[-1]
            if token in self._finished:
                self._stack.pop()
                self._finished.remove(token)
            else:
                break

    def _refresh(self):
        self._clean_stack_top()

        if not self._stack:
            self._finished.clear()
            if self._live_status:
                self._live_status.stop()
                self._live_status = None
        else:
            _, text = self._stack[-1]
            if self._live_status is None:
                self._live_status = Status(text, console=self.console)
                self._live_status.start()
            else:
                self._live_status.update(text)

    @contextmanager
    def status(self, text):
        token = object()

        self._stack.append((token, text))
        self._refresh()

        try:
            yield
        finally:
            self._finished.add(token)
            self._refresh()


def apply_status_patch(console_instance):
    """
    为 Console.status() 提供可嵌套支持，避免在 asyncio 并发场景下触发 LiveError。

    前提与限制：
    - 仅适用于单线程 asyncio 应用
    - 所有协程必须复用同一个 Console 实例
    """
    manager = _StackedStatusManager(console_instance)
    console_instance.status = manager.status


def apply_argparse_patch(p: argparse.ArgumentParser):
    """
    为 ArgumentParser 提供工具调用的补丁。
    """
    # 正常模式直接跳过
    if "toolcall" not in sys.argv:
        return

    if not isinstance(p, AgentFriendlyParserMixin):
        p.__class__ = type(
            f"AgentFriendly{p.__class__.__name__}",
            (AgentFriendlyParserMixin, p.__class__),
            {}
        )

    # 处理 subparsers (如果存在)
    if p._subparsers is not None:
        for action in p._subparsers._group_actions:
            if isinstance(action, argparse._SubParsersAction):
                for sub_p in action.choices.values():
                    apply_argparse_patch(sub_p)


class AgentFriendlyParserMixin:
    """
    混入类，仅在 toolcall 模式下被混入（由 apply_argparse_patch 守卫），
    """

    def error(self, message: str):
        response = {"code": 13, "msg": message, "data": None}
        sys.stderr.write(json.dumps(response, ensure_ascii=False, indent=2) + "\n")
        sys.exit(1)

    def print_help(self, file=None):
        response = {
            "code": 0,
            "msg": "usage_info",
            "data": _extract_semantic_help(self)
        }
        sys.stdout.write(json.dumps(response, ensure_ascii=False, indent=2) + "\n")
        sys.exit(0)


def _extract_semantic_help(p: argparse.ArgumentParser) -> dict:
    """
    从解析器提取语义化信息的原子函数。
    """
    help_data = {
        "prog": p.prog,
        "description": p.description,
        "usage": p.format_usage().strip(),
        "arguments": [],
        "subcommands": []
    }

    for action in p._actions:
        if isinstance(action, argparse._HelpAction):
            continue

        if isinstance(action, argparse._SubParsersAction):
            help_data["subcommands"] = list(action.choices.keys())
            continue

        help_data["arguments"].append({
            "names": action.option_strings,
            "dest": action.dest,
            "help": action.help,
            "required": action.required,
            "default": action.default if action.default is not argparse.SUPPRESS else None
        })

    return help_data
