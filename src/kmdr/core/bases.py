import os

from typing import Callable, Optional
import asyncio
from aiohttp import ClientSession

from .error import LoginError
from .registry import Registry
from .structure import VolInfo, BookInfo
from .utils import construct_callback
from .defaults import Configurer as InnerConfigurer, UserProfile, session_var

class SessionContext:

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._session: ClientSession = session_var.get()

class UserProfileContext:

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._profile = UserProfile()

class ConfigContext:

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._configurer = InnerConfigurer()

class Configurer(ConfigContext):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def operate(self) -> None: ...

class Authenticator(SessionContext, ConfigContext, UserProfileContext):

    def __init__(self, proxy: Optional[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # if proxy:
        #     self._session.proxies.update({
        #         'https': proxy,
        #         'http': proxy,
        #     })

    # 在使用代理登录时，可能会出现问题，但是现在还不清楚是不是代理的问题。
    # 主站正常情况下不使用代理也能登录成功。但是不排除特殊的网络环境下需要代理。
    # 所以暂时保留代理登录的功能，如果后续确认是代理的问题，可以考虑启用 @no_proxy 装饰器。
    # @no_proxy
    async def authenticate(self) -> None:
        try:
            assert await self._authenticate()
        except LoginError as e:
            print("Authentication failed. Please check your login credentials or session cookies.")
            print(f"Details: {e}")
            exit(1)

    async def _authenticate(self) -> bool: ...

class Lister(SessionContext):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def list(self) -> tuple[BookInfo, list[VolInfo]]: ...

class Picker:

    def __init__(self, *args, **kwargs):
        super().__init__()

    def pick(self, volumes: list[VolInfo]) -> list[VolInfo]: ...

class Downloader(SessionContext, UserProfileContext):

    def __init__(self,
                 dest: str = '.',
                 callback: Optional[str] = None,
                 retry: int = 3,
                 num_workers: int = 8,
                 proxy: Optional[str] = None,
                 *args, **kwargs
    ):
        SessionContext.__init__(self)
        UserProfileContext.__init__(self)

        self._dest: str = dest
        self._callback: Optional[Callable] = construct_callback(callback)
        self._retry: int = retry
        self._num_workers: int = num_workers
        self._proxy: Optional[str] = proxy

    async def download(self, book: BookInfo, volumes: list[VolInfo]):
        """
        下载指定卷的主入口方法。
        """
        if not volumes:
            raise ValueError("No volumes to download")

        semaphore = asyncio.Semaphore(self._num_workers)
        async def download_with_semaphore(volume: VolInfo):
            async with semaphore:
                return await self._download(book, volume, self._retry)

        try:
            tasks = [download_with_semaphore(volume) for volume in volumes]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"下载 '{volumes[i].name}' 失败: {result}")

        except KeyboardInterrupt:
            print("\n操作已取消（KeyboardInterrupt）")
            exit(130)

    async def _download(self, book: BookInfo, volume: VolInfo, retry: int): ...

AUTHENTICATOR = Registry[Authenticator]('Authenticator')
LISTERS = Registry[Lister]('Lister')
PICKERS = Registry[Picker]('Picker')
DOWNLOADER = Registry[Downloader]('Downloader', True)
CONFIGURER = Registry[Configurer]('Configurer')