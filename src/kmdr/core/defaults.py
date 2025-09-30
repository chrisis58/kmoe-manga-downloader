import os
import json
from typing import Optional, Any
import argparse
from contextvars import ContextVar
from rich.console import Console
from rich.progress import (
    Progress,
    BarColumn,
    DownloadColumn,
    TextColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)

from .utils import singleton
from .structure import Config
from .constants import BASE_URL

HEADERS = {
    'User-Agent': 'kmdr/1.0 (https://github.com/chrisis58/kmoe-manga-downloader)'
}

console = Console()

def console_print(*args, **kwargs):
    console.print(*args, **kwargs)

progress = Progress(
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
    console=console,
)

session_var = ContextVar('session')

parser: Optional[argparse.ArgumentParser] = None
args: Optional[argparse.Namespace] = None

def argument_parser():
    global parser
    if parser is not None:
        return parser

    parser = argparse.ArgumentParser(description='Kmoe 漫画下载器')
    subparsers = parser.add_subparsers(title='可用的子命令', dest='command')

    download_parser = subparsers.add_parser('download', help='下载指定的漫画')
    download_parser.add_argument('-d', '--dest', type=str, help='指定下载文件的保存路径，默认为当前目录', required=False)
    download_parser.add_argument('-l', '--book-url', type=str, help='漫画详情页面的 URL', required=False)
    download_parser.add_argument('-v', '--volume', type=str, help='指定下载的卷，多个用逗号分隔，例如 `1,2,3` 或 `1-5,8`，`all` 表示全部', required=False)
    download_parser.add_argument('-t', '--vol-type', type=str, help='指定下载的卷类型，`vol` 为单行本, `extra` 为番外, `seri` 为连载', required=False, choices=['vol', 'extra', 'seri', 'all'], default='vol')
    download_parser.add_argument('--max-size', type=float, help='限制下载卷的最大体积 (单位: MB)', required=False)
    download_parser.add_argument('--limit', type=int, help='限制下载卷的总数量', required=False)
    download_parser.add_argument('--num-workers', type=int, help='下载时使用的并发任务数', required=False)
    download_parser.add_argument('-p', '--proxy', type=str, help='设置下载使用的代理服务器', required=False)
    download_parser.add_argument('-r', '--retry', type=int, help='网络请求失败时的重试次数', required=False)
    download_parser.add_argument('-c', '--callback', type=str, help='每个卷下载完成后执行的回调脚本，例如: `echo {v.name} downloaded!`', required=False)

    login_parser = subparsers.add_parser('login', help='登录到 Kmoe')
    login_parser.add_argument('-u', '--username', type=str, help='用户名', required=True)
    login_parser.add_argument('-p', '--password', type=str, help='密码 (如果留空，应用将提示您输入)', required=False)

    status_parser = subparsers.add_parser('status', help='显示账户信息以及配额')
    status_parser.add_argument('-p', '--proxy', type=str, help='代理服务器', required=False)

    config_parser = subparsers.add_parser('config', help='配置下载器')
    config_parser.add_argument('-l', '--list-option', action='store_true', help='列出所有配置')
    config_parser.add_argument('-s', '--set', nargs='+', type=str, help='设置一个或多个配置项，格式为 `key=value`，例如: `num_workers=8`')
    config_parser.add_argument('-b', '--base-url', type=str, help='设置镜像站点的基础 URL, 例如: `https://kxx.moe`')
    config_parser.add_argument('-c', '--clear', type=str, help='清除指定配置，可选值为 `all`, `cookie`, `option`')
    config_parser.add_argument('-d', '--delete', '--unset', dest='unset', type=str, help='删除特定的配置选项')

    return parser

def parse_args():
    global args
    if args is not None:
        return args

    parser = argument_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        exit(1)

    return args

@singleton
class UserProfile:

    def __init__(self):
        self._is_vip: Optional[int] = None
        self._user_level: Optional[int] = None

    @property
    def is_vip(self) -> Optional[int]:
        return self._is_vip

    @property
    def user_level(self) -> Optional[int]:
        return self._user_level
    
    @is_vip.setter
    def is_vip(self, value: Optional[int]):
        self._is_vip = value

    @user_level.setter
    def user_level(self, value: Optional[int]):
        self._user_level = value

@singleton
class Configurer:

    def __init__(self):
        self.__filename = '.kmdr'

        if not os.path.exists(os.path.join(os.path.expanduser("~"), self.__filename)):
            self._config = Config()
            self.update()
        else:
            with open(os.path.join(os.path.expanduser("~"), self.__filename), 'r') as f:
                config = json.load(f)

            self._config = Config()
            option = config.get('option', None)
            if option is not None and isinstance(option, dict):
                self._config.option = option
            cookie = config.get('cookie', None)
            if cookie is not None and isinstance(cookie, dict):
                self._config.cookie = cookie
            base_url = config.get('base_url', None)
            if base_url is not None and isinstance(base_url, str):
                self._config.base_url = base_url

    @property
    def config(self) -> 'Config':
        return self._config
    
    @property
    def cookie(self) -> Optional[dict]:
        if self._config is None:
            return None
        return self._config.cookie
    
    @cookie.setter
    def cookie(self, value: Optional[dict[str, str]]):
        if self._config is None:
            self._config = Config()
        self._config.cookie = value
        self.update()
    
    @property
    def option(self) -> Optional[dict]:
        if self._config is None:
            return None
        return self._config.option
    
    @option.setter
    def option(self, value: Optional[dict[str, Any]]):
        if self._config is None:
            self._config = Config()
        self._config.option = value
        self.update()
    
    @property
    def base_url(self) -> str:
        if self._config is None or self._config.base_url is None:
            return BASE_URL.DEFAULT 
        return self._config.base_url
    
    def set_base_url(self, value: str):
        if self._config is None:
            self._config = Config()
        self._config.base_url = value
        self.update()
    
    def update(self):
        with open(os.path.join(os.path.expanduser("~"), self.__filename), 'w') as f:
            json.dump(self._config.__dict__, f, indent=4, ensure_ascii=False)
    
    def clear(self, key: str):
        if key == 'all':
            self._config = Config()
        elif key == 'cookie':
            self._config.cookie = None
        elif key == 'option':
            self._config.option = None
        else:
            raise KeyError(f"[red]对应配置不存在: {key}。可用配置项：all, cookie, option[/red]")

        self.update()
    
    def set_option(self, key: str, value: Any):
        if self._config.option is None:
            self._config.option = {}

        self._config.option[key] = value
        self.update()
    
    def unset_option(self, key: str):
        if self._config.option is None or key not in self._config.option:
            return
        
        del self._config.option[key]
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

base_url_var = ContextVar('base_url', default=Configurer().base_url)
