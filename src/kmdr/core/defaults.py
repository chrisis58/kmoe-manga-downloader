import os
import json
from typing import Optional
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


console = Console()

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

    parser = argparse.ArgumentParser(description='Kox Downloader')
    subparsers = parser.add_subparsers(title='subcommands', dest='command')

    download_parser = subparsers.add_parser('download', help='Download books')
    download_parser.add_argument('-d', '--dest', type=str, help='Download destination, default to current directory', required=False)
    download_parser.add_argument('-l', '--book-url', type=str, help='Book page\'s url', required=False)
    download_parser.add_argument('-v', '--volume', type=str, help='Volume(s), split using commas, `all` for all', required=False)
    download_parser.add_argument('-t', '--vol-type', type=str, help='Volume type, `vol` for volume, `extra` for extras, `seri` for serialized', required=False, choices=['vol', 'extra', 'seri', 'all'], default='vol')
    download_parser.add_argument('--max-size', type=float, help='Max size of volume in MB', required=False)
    download_parser.add_argument('--limit', type=int, help='Limit number of volumes to download', required=False)
    download_parser.add_argument('--num-workers', type=int, help='Number of workers to use for downloading', required=False)
    download_parser.add_argument('-p', '--proxy', type=str, help='Proxy server', required=False)
    download_parser.add_argument('-r', '--retry', type=int, help='Retry times', required=False)
    download_parser.add_argument('-c', '--callback', type=str, help='Callback script, use as `echo {v.name} downloaded!`', required=False)

    login_parser = subparsers.add_parser('login', help='Login to kox.moe')
    login_parser.add_argument('-u', '--username', type=str, help='Your username', required=True)
    login_parser.add_argument('-p', '--password', type=str, help='Your password', required=False)

    status_parser = subparsers.add_parser('status', help='Show status of account and script')
    status_parser.add_argument('-p', '--proxy', type=str, help='Proxy server', required=False)

    config_parser = subparsers.add_parser('config', help='Configure the downloader')
    config_parser.add_argument('-l', '--list-option', action='store_true', help='List all configurations')
    config_parser.add_argument('-s', '--set', nargs='+', type=str, help='Configuration options to set, e.g. num_workers=3 dest=.')
    config_parser.add_argument('-c', '--clear', type=str, help='Clear configurations, `all`, `cookie`, `option` are available')
    config_parser.add_argument('-d', '--delete', '--unset', dest='unset', type=str, help='Delete a specific configuration option')

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
    def option(self, value: Optional[dict[str, any]]):
        if self._config is None:
            self._config = Config()
        self._config.option = value
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
            raise ValueError(f"Unsupported clear option: {key}")

        self.update()
    
    def set_option(self, key: str, value: any):
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
    option = Configurer().config.option
    return __combine_args(dest, option)