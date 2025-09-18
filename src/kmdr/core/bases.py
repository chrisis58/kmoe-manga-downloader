from typing import Callable, Optional
from abc import abstractmethod

import asyncio
from aiohttp import ClientSession

from .error import LoginError
from .registry import Registry
from .structure import VolInfo, BookInfo
from .utils import construct_callback

from .context import TerminalContext, SessionContext, UserProfileContext, ConfigContext

class Configurer(ConfigContext, TerminalContext):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    @abstractmethod
    def operate(self) -> None: ...

class Authenticator(SessionContext, ConfigContext, UserProfileContext, TerminalContext):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    # 在使用代理登录时，可能会出现问题，但是现在还不清楚是不是代理的问题。
    # 主站正常情况下不使用代理也能登录成功。但是不排除特殊的网络环境下需要代理。
    # 所以暂时保留代理登录的功能，如果后续确认是代理的问题，可以考虑启用 @no_proxy 装饰器。
    # @no_proxy
    async def authenticate(self) -> None:
        with self._console.status("认证中..."):
            try:
                assert await self._authenticate()
            except LoginError as e:
                self._console.print("[red]认证失败。请检查您的登录凭据或会话 cookie。[/red]")
                self._console.print(f"[yellow]详细信息：{e}[/yellow]")
                exit(1)

    @abstractmethod
    async def _authenticate(self) -> bool: ...

class Lister(SessionContext, TerminalContext):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @abstractmethod
    async def list(self) -> tuple[BookInfo, list[VolInfo]]: ...

class Picker(TerminalContext):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @abstractmethod
    def pick(self, volumes: list[VolInfo]) -> list[VolInfo]: ...

class Downloader(SessionContext, UserProfileContext, TerminalContext):

    def __init__(self,
                 dest: str = '.',
                 callback: Optional[str] = None,
                 retry: int = 3,
                 num_workers: int = 8,
                 *args, **kwargs
    ):
        super().__init__(*args, **kwargs)

        self._dest: str = dest
        self._callback: Optional[Callable] = construct_callback(callback)
        self._retry: int = retry
        self._semaphore = asyncio.Semaphore(num_workers)

    async def download(self, book: BookInfo, volumes: list[VolInfo]):
        if not volumes:
            self._console.print("No volumes to download.")
            exit(0)

        try:
            with self._progress:
                tasks = [self._download(book, volume) for volume in volumes]
                await asyncio.gather(*tasks, return_exceptions=True)

        except KeyboardInterrupt:
            self._console.print("\n操作已取消（KeyboardInterrupt）")
            exit(130)

    @abstractmethod
    async def _download(self, book: BookInfo, volume: VolInfo): ...

KMDR_SESSION = Registry[ClientSession]('KmdrSession', True)
AUTHENTICATOR = Registry[Authenticator]('Authenticator')
LISTERS = Registry[Lister]('Lister')
PICKERS = Registry[Picker]('Picker')
DOWNLOADER = Registry[Downloader]('Downloader', True)
CONFIGURER = Registry[Configurer]('Configurer')