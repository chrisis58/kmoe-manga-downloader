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

from .context import TerminalContext, SessionContext, ConfigContext, CredentialPoolContext

class Configurer(ConfigContext, TerminalContext):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def operate(self) -> None:
        try:
            self._operate()
        finally:
            self._configurer.update()

    @abstractmethod
    def _operate(self) -> None: ...

class PoolManager(CredentialPoolContext, TerminalContext):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @abstractmethod
    async def operate(self) -> None: ...

class SessionManager(SessionContext, ConfigContext, TerminalContext):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @abstractmethod
    async def session(self) -> AsyncCtxManager[ClientSession]: ...

class Authenticator(SessionContext, ConfigContext, TerminalContext):

    def __init__(self, auto_save: bool, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._auto_save = auto_save

    async def authenticate(self) -> Credential:
        with self._console.status("认证中..."):
            try:
                cred = await async_retry()(self._authenticate)()
                assert cred is not None

                # 保存凭证信息
                if self._auto_save:
                    self._configurer.save_credential(cred, as_primary=True)
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
        avai = self._avai_quota(cred)
        if avai < total_size:
            if self._console.is_interactive:
                should_continue = Confirm.ask(
                    f"[red]警告：当前下载所需额度约为 {total_size:.2f} MB，当前剩余额度 {avai:.2f} MB，可能无法正常完成下载。是否继续下载？[/red]",
                    default=False
                )
                
                if not should_continue:
                    info("用户取消下载。")
                    return
            else:
                log(f"[red]警告：当前下载所需额度约为 {total_size:.2f} MB，当前剩余额度 {avai:.2f} MB，可能无法正常完成下载。[/red]")

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

    def _avai_quota(self, cred: Credential) -> float:
        """计算并返回指定 Credential 的可用额度（单位：MB）"""
        return cred.quota_remaining

    @abstractmethod
    async def _download(self, cred: Credential, book: BookInfo, volume: VolInfo, quota_deduct_callback: Optional[Callable[[bool], None]] = None):
        """
        供子类实现的实际下载方法。

        :param cred: 用于下载的凭证
        :param book: 要下载的书籍信息
        :param volume: 要下载的卷信息
        :param quota_deduct_callback: 可选的额度扣除回调函数，接受一个布尔值参数，表示额度是否被扣除
        """
        ...


SESSION_MANAGER = Registry[SessionManager]('SessionManager', True)
AUTHENTICATOR = Registry[Authenticator]('Authenticator')
LISTERS = Registry[Lister]('Lister')
PICKERS = Registry[Picker]('Picker')
DOWNLOADER = Registry[Downloader]('Downloader', True)
CONFIGURER = Registry[Configurer]('Configurer')
POOL_MANAGER = Registry[PoolManager]('PoolManager')