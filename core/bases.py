from typing import Callable, Optional

from .registry import Registry
from .structure import VolInfo, BookInfo, Config
from .utils import get_singleton_session
from .defaults import Configurer

class SessionContext:

    def __init__(self, *args, **kwargs):
        self._session = get_singleton_session()

class ConfigContext:

    def __init__(self, *args, **kwargs):
        self._configurer = Configurer()

class Authenticator(SessionContext, ConfigContext):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def authenticate(self, *args, **kwargs) -> bool: ...

class Lister(SessionContext):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self, *args, **kwargs) -> tuple[BookInfo, list[VolInfo]]: ...

class Picker(SessionContext):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def pick(self, volumes: list[VolInfo], *args, **kwargs) -> list[VolInfo]: ...

class Downloader(SessionContext):

    def __init__(self, 
            dest: str,
            callback: Optional[Callable[[VolInfo], None]] = None,
            retry: int = 3,
            *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._dest: str = dest
        self._callback: Optional[Callable[[VolInfo], None]] = callback
        self._retry: int = retry

    def download(self, book: BookInfo, volumes: list[VolInfo], *args, **kwargs): ...

AUTHENTICATOR = Registry[Authenticator]('Authenticator')
LISTERS = Registry[Lister]('Lister')
PICKERS = Registry[Picker]('Picker')
DOWNLOADER = Registry[Downloader]('Downloader')