from abc import abstractmethod
from collections.abc import Awaitable
from typing import Callable

from aiohttp import ClientSession

from .console import info
from .context import (
    ConfigContext,
    CredentialPoolContext,
    SessionContext,
    TerminalContext,
)
from .error import LoginError
from .protocol import AsyncCtxManager
from .registry import Registry
from .structure import BookInfo, Credential, VolInfo
from .utils import async_retry


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
    async def list(self, awaitable_cred: Callable[[], Awaitable[Credential]]) -> tuple[BookInfo, list[VolInfo]]: ...


class Cataloger(SessionContext, TerminalContext):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @abstractmethod
    async def catalog(self, awaitable_cred: Callable[[], Awaitable[Credential]]) -> list[BookInfo]: ...


class Picker(TerminalContext):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @abstractmethod
    def pick(self, volumes: list[VolInfo]) -> list[VolInfo]: ...


class Downloader(SessionContext, TerminalContext):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @abstractmethod
    async def download(self, cred: Credential, book: BookInfo, volumes: list[VolInfo]) -> None:
        """
        供具体下载器实现的接口方法。
        :param cred: 下载凭证
        :param book: 书籍信息
        :param volumes: 需要下载的卷列表
        """
        ...


SESSION_MANAGER = Registry[SessionManager]("SessionManager", True)
AUTHENTICATOR = Registry[Authenticator]("Authenticator")
LISTERS = Registry[Lister]("Lister")
PICKERS = Registry[Picker]("Picker")
DOWNLOADER = Registry[Downloader]("Downloader", True)
CONFIGURER = Registry[Configurer]("Configurer")
POOL_MANAGER = Registry[PoolManager]("PoolManager")
CATALOGERS = Registry[Cataloger]("Cataloger", True)
