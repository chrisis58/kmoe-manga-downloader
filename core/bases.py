import os

from typing import Callable, Optional

from .registry import Registry
from .structure import VolInfo, BookInfo, Config
from .utils import get_singleton_session, construct_callback
from .defaults import Configurer as InnerConfigurer

class SessionContext:

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._session = get_singleton_session()

class ConfigContext:

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._configurer = InnerConfigurer()

class Configurer(ConfigContext):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def operate(self) -> None: ...

class Authenticator(SessionContext, ConfigContext):

    def __init__(self, proxy: Optional[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if proxy:
            self._session.proxies.update({
                'https': proxy,
                'http': proxy,
            })

    def authenticate(self) -> bool: ...

class Lister(SessionContext):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self) -> tuple[BookInfo, list[VolInfo]]: ...

class Picker(SessionContext):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def pick(self, volumes: list[VolInfo]) -> list[VolInfo]: ...

class Downloader(SessionContext):

    def __init__(self, 
            dest: str = '.',
            callback: Optional[str] = None,
            retry: int = 3,
            num_workers: int = 1,
            *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._dest: str = dest
        self._callback: Optional[Callable[[BookInfo, VolInfo], int]] = construct_callback(callback)
        self._retry: int = retry
        self._num_workers: int = num_workers

    def download(self, book: BookInfo, volumes: list[VolInfo]):
        if volumes is None or not volumes:
            raise ValueError("No volumes to download")

        if self._num_workers <= 1:
            for volume in volumes:
                self._download(book, volume, self._retry)
        else:
            self._download_with_multiple_workers(book, volumes, self._retry)

    def _download(self, book: BookInfo, volume: VolInfo, retry: int): ...

    def _download_with_multiple_workers(self, book: BookInfo, volumes: list[VolInfo], retry: int):
        from concurrent.futures import ThreadPoolExecutor

        max_workers = min(self._num_workers, len(volumes))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self._download, book, volume, retry)
                for volume in volumes
            ]
            for future in futures:
                future.result()

AUTHENTICATOR = Registry[Authenticator]('Authenticator')
LISTERS = Registry[Lister]('Lister')
PICKERS = Registry[Picker]('Picker')
DOWNLOADER = Registry[Downloader]('Downloader', True)
CONFIGURER = Registry[Configurer]('Configurer')