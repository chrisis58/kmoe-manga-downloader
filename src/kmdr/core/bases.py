from typing import Callable, Optional
from abc import abstractmethod

import asyncio
from aiohttp import ClientSession
from rich.prompt import Confirm

from .console import *
from .error import LoginError
from .registry import Registry
from .structure import VolInfo, BookInfo, Credential
from .utils import construct_callback, async_retry
from .protocol import AsyncCtxManager

from .context import TerminalContext, SessionContext, ConfigContext

class Configurer(ConfigContext, TerminalContext):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    @abstractmethod
    def operate(self) -> None: ...

class SessionManager(SessionContext, ConfigContext, TerminalContext):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @abstractmethod
    async def session(self) -> AsyncCtxManager[ClientSession]: ...

class Authenticator(SessionContext, ConfigContext, TerminalContext):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    # 在使用代理登录时，可能会出现问题，但是现在还不清楚是不是代理的问题。
    # 主站正常情况下不使用代理也能登录成功。但是不排除特殊的网络环境下需要代理。
    # 所以暂时保留代理登录的功能，如果后续确认是代理的问题，可以考虑启用 @no_proxy 装饰器。
    # @no_proxy
    async def authenticate(self) -> Credential:
        with self._console.status("认证中..."):
            try:
                cred = await async_retry()(self._authenticate)()
                assert cred is not None
                self._credential = cred
                return cred
            except LoginError:
                info("[red]认证失败。请检查您的登录凭据或会话 cookie。[/red]")
                raise

    @abstractmethod
    async def _authenticate(self) -> Credential: ...

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

class Downloader(SessionContext, TerminalContext):

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

    async def download(self, cred: Credential, book: BookInfo, volumes: list[VolInfo]):
        if not volumes:
            info("没有可下载的卷。", style="blue")
            return
        
        total_size = sum(v.size or 0 for v in volumes)
        if total_size > cred.quota_remaining:
            if self._console.is_interactive:
                should_continue = Confirm.ask(
                    f"[red]警告：当前下载所需额度约为 {total_size:.2f} MB，当前剩余额度 {cred.quota_remaining:.2f} MB，可能无法正常完成下载。是否继续下载？[/red]",
                    default=False
                )
                
                if not should_continue:
                    info("用户取消下载。")
                    return
            else:
                log(f"[red]警告：当前下载所需额度约为 {total_size:.2f} MB，当前剩余额度 {cred.quota_remaining:.2f} MB，可能无法正常完成下载。[/red]")

        try:
            with self._progress:
                tasks = [self._download(cred, book, volume) for volume in volumes]
                results = await asyncio.gather(*tasks, return_exceptions=True)

            exceptions = [res for res in results if isinstance(res, Exception)]
            if exceptions:
                info(f"[red]下载过程中出现 {len(exceptions)} 个错误：[/red]")
                for exc in exceptions:
                    info(f"[red]- {exc}[/red]")
                    exception(exc)

        except asyncio.CancelledError:
            await asyncio.sleep(0.01)
            raise

    @abstractmethod
    async def _download(self, cred: Credential, book: BookInfo, volume: VolInfo): ...

SESSION_MANAGER = Registry[SessionManager]('SessionManager', True)
AUTHENTICATOR = Registry[Authenticator]('Authenticator')
LISTERS = Registry[Lister]('Lister')
PICKERS = Registry[Picker]('Picker')
DOWNLOADER = Registry[Downloader]('Downloader', True)
CONFIGURER = Registry[Configurer]('Configurer')