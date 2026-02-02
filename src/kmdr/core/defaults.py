import dataclasses
from enum import Enum
import os
import json
from typing import Optional, Any
import argparse
from contextvars import ContextVar

from rich.progress import (
    BarColumn,
    DownloadColumn,
    TextColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)

from .utils import singleton
from .structure import Config, Credential
from .constants import BASE_URL
from .console import _update_verbose_setting
from .error import InitializationError

TRUE_UA = "kmdr/1.0 (https://github.com/chrisis58/kmoe-manga-downloader)"


progress_definition = (
    TextColumn("[blue]{task.fields[filename]}", justify="left"),
    TextColumn("{task.fields[status]}", justify="right"),
    TextColumn("{task.percentage:>3.1f}%"),
    BarColumn(bar_width=None),
    "[progress.percentage]",
    DownloadColumn(),
    "[",
    TransferSpeedColumn(),
    ",",
    TimeRemainingColumn(),
    "]",
)

session_var = ContextVar("session")

parser: Optional[argparse.ArgumentParser] = None
args: Optional[argparse.Namespace] = None


# fmt: off
def argument_parser():
    global parser
    if parser is not None:
        return parser

    parser = argparse.ArgumentParser(description="Kmoe 漫画下载器")

    parser.add_argument("-v", "--verbose", action="store_true", help="启用详细输出")

    subparsers = parser.add_subparsers(title="可用的子命令", dest="command")

    subparsers.add_parser("version", help="显示当前版本信息")

    download_parser = subparsers.add_parser("download", help="下载指定的漫画")
    download_parser.add_argument("-d", "--dest", type=str, help="指定下载文件的保存路径，默认为当前目录", required=False)
    download_parser.add_argument("-l", "--book-url", type=str, help="漫画详情页面的 URL", required=False)
    download_parser.add_argument("-v", "--volume", type=str, help="指定下载的卷，多个用逗号分隔，例如 `1,2,3` 或 `1-5,8`，`all` 表示全部", required=False)
    download_parser.add_argument("-t", "--vol-type", type=str, help="指定下载的卷类型，`vol` 为单行本, `extra` 为番外, `seri` 为连载", required=False, choices=["vol", "extra", "seri", "all"], default="vol")
    download_parser.add_argument("--max-size", type=float, help="限制下载卷的最大体积 (单位: MB)", required=False)
    download_parser.add_argument("--limit", type=int, help="限制下载卷的总数量", required=False)
    download_parser.add_argument("--num-workers", type=int, help="下载时使用的并发任务数", required=False)
    download_parser.add_argument("-p", "--proxy", type=str, help="设置下载使用的代理服务器", required=False)
    download_parser.add_argument("-r", "--retry", type=int, help="网络请求失败时的重试次数", required=False)
    download_parser.add_argument("-c", "--callback", type=str, help="每个卷下载完成后执行的回调脚本，例如: `echo {v.name} downloaded!`", required=False)
    download_parser.add_argument("-m", "--method", type=int, help="下载方法，对应网站上的不同下载方式", required=False, choices=[1, 2], default=1)
    download_parser.add_argument("--vip", action="store_true", help="尝试使用 VIP 链接进行下载（下载速度可能不及 CDN 方式）")
    download_parser.add_argument("--disable-multi-part", action="store_true", help="禁用分片下载，优先级高于尝试启用分片下载选项")
    download_parser.add_argument("--try-multi-part", action="store_true", help="尝试启用分片下载")
    download_parser.add_argument("--fake-ua", action="store_true", help="使用随机的 User-Agent 进行请求")
    download_parser.add_argument("-P", "--use-pool", action="store_true", help="启用凭证池进行下载")
    download_parser.add_argument("--per-cred-ratio", type=float, help="启用凭证池时生效，设定每个凭证的最大并发比例，默认为 1.0。如 `num_workers` 设定为 8，`per_cred_ratio` 设定为 0.5，则每个凭证最多使用 4 个并发任务。", required=False, default=1.0)

    login_parser = subparsers.add_parser("login", help="登录到 Kmoe")
    login_parser.add_argument("-u", "--username", type=str, help="用户名", required=True)
    login_parser.add_argument("-p", "--password", type=str, help="密码 (如果留空，应用将提示您输入)", required=False)

    status_parser = subparsers.add_parser("status", help="显示账户信息以及配额")
    status_parser.add_argument("-p", "--proxy", type=str, help="代理服务器", required=False)

    config_parser = subparsers.add_parser("config", help="配置下载器")
    config_parser.add_argument("-l", "--list-option", action="store_true", help="列出所有配置")
    config_parser.add_argument("-s", "--set", nargs="+", type=str, help="设置一个或多个配置项，格式为 `key=value`，例如: `num_workers=8`")
    config_parser.add_argument("-b", "--base-url", type=str, help="设置镜像站点的基础 URL, 例如: `https://kxx.moe`")
    config_parser.add_argument("-c", "--clear", type=str, help="清除指定配置，可选值为 `all`, `cookie`, `option`")
    config_parser.add_argument("-d", "--delete", "--unset", dest="unset", type=str, help="删除特定的配置选项")

    pool_parser = subparsers.add_parser("pool", aliases=["profile"], help="管理凭证池")
    
    pool_subparsers = pool_parser.add_subparsers(title="凭证池操作", dest="pool_command")

    pool_add = pool_subparsers.add_parser("add", help="向池中添加账号")
    pool_add.add_argument("-u", "--username", type=str, required=True, help="用户名")
    pool_add.add_argument("-p", "--password", type=str, help="密码")
    pool_add.add_argument("-o", "--order", type=int, default=0, help="账号优先级，数值越小优先级越高")
    pool_add.add_argument("-n", "--note", type=str, help="备注信息")

    pool_remove = pool_subparsers.add_parser("remove", help="从池中移除账号")
    pool_remove.add_argument("username", type=str, help="要移除的用户名")

    pool_list = pool_subparsers.add_parser("list", help="列出池中所有账号")
    pool_list.add_argument("-r", "--refresh", action="store_true", help="刷新所有账号的状态和配额信息")
    pool_list.add_argument("--num-workers", type=int, default=3, help="刷新时使用的并发任务数，默认为 3")

    pool_use = pool_subparsers.add_parser("use", help="将池中指定账号应用为当前默认账号")
    pool_use.add_argument("username", type=str, help="要切换使用的用户名")

    pool_update = pool_subparsers.add_parser("update", help="更新池中指定账号的信息")
    pool_update.add_argument("username", type=str, help="要更新的用户名")
    pool_update.add_argument("-n", "--note", type=str, help="更新备注信息")
    pool_update.add_argument("-o", "--order", type=int, help="更新账号优先级，数值越小优先级越高")

    return parser
# fmt: on


def parse_args():
    global args
    if args is not None:
        return args

    parser = argument_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()

    return args


class KmdrJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)

        if isinstance(o, Enum):
            return o.value

        return super().default(o)


@singleton
class Configurer:
    def __init__(self):
        self.__filename = ".kmdr"

        if not os.path.exists(os.path.join(os.path.expanduser("~"), self.__filename)):
            self._config: Config = Config()
            self.update()
        else:
            with open(os.path.join(os.path.expanduser("~"), self.__filename), "r") as f:
                config_data = json.load(f)
            self._config: Config = Config.from_dict(config_data)

        if self._config is None:
            raise InitializationError("无法加载配置文件。")

    @property
    def config(self) -> "Config":
        return self._config

    @property
    def cookie(self) -> Optional[dict]:
        return self._config.cookie

    @cookie.setter
    def cookie(self, value: Optional[dict[str, str]]):
        self._config.cookie = value

    @property
    def option(self) -> dict:
        if self._config.option is None:
            self._config.option = {}
        return self._config.option

    @property
    def base_url(self) -> str:
        if self._config.base_url is None:
            return BASE_URL.DEFAULT.value
        return self._config.base_url

    def set_base_url(self, value: str):
        self._config.base_url = value

    def update(self):
        with open(os.path.join(os.path.expanduser("~"), self.__filename), "w") as f:
            json.dump(
                self._config.__dict__,
                f,
                cls=KmdrJSONEncoder,
                indent=4,
                ensure_ascii=False,
            )

    def clear(self, key: str):
        if key == "all":
            self._config = Config()
        elif key == "cookie":
            self._config.cookie = None
            self._config.username = None
        elif key == "option":
            self._config.option = None
        else:
            raise KeyError(f"[red]对应配置不存在: {key}。可用配置项：all, cookie, option[/red]")

    def set_option(self, key: str, value: Any):
        if self._config.option is None:
            self._config.option = {}

        self._config.option[key] = value

    def unset_option(self, key: str):
        if self._config.option is None or key not in self._config.option:
            return

        del self._config.option[key]

    def save_credential(self, cred: Credential, as_primary: bool = False) -> None:
        """
        保存凭证到配置文件中的凭证池中。<br/>
        可能对凭证池不可见，如果要确保凭证池更新，应刷新凭证池实例。

        :param cred: 要保存的凭证对象
        :param as_primary: 是否将该凭证设置为主凭证
        """

        if as_primary:
            self._config.cookie = cred.cookies
            self._config.username = cred.username

        if self._config.cred_pool is None:
            self._config.cred_pool = []

        for idx, c in enumerate(self._config.cred_pool):
            if c.username == cred.username:
                self._config.cred_pool[idx] = cred
                self.update()
                return

        self._config.cred_pool.append(cred)
        self.update()


def __combine_args(dest: argparse.Namespace, option: dict) -> argparse.Namespace:
    if option is None:
        return dest

    for key, value in option.items():
        if hasattr(dest, key) and getattr(dest, key) is None:
            setattr(dest, key, value)
    return dest


def combine_args(dest: argparse.Namespace) -> argparse.Namespace:
    assert isinstance(dest, argparse.Namespace), "dest must be an argparse.Namespace instance"
    option = Configurer().option

    if option is None:
        return dest

    return __combine_args(dest, option)


base_url_var = ContextVar("base_url", default=Configurer().base_url)


def post_init(args) -> None:
    _verbose = getattr(args, "verbose", False)
    _update_verbose_setting(_verbose)
