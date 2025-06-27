from typing import Callable, Optional

from .structure import VolInfo, BookInfo
from .utils import get_singleton_session

class SessionContext:

    def __init__(self, *args, **kwargs):
        self._session = get_singleton_session()

class Authenticator(SessionContext):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def authenticate(self, *args, **kwargs) -> bool:
        raise NotImplementedError("Subclasses must implement this method.")

class Lister(SessionContext):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def list(self, *args, **kwargs) -> list[VolInfo]:
        raise NotImplementedError("Subclasses must implement this method.")

class Picker(SessionContext):

    def __init__(self, volumes: list[VolInfo], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._volumes = volumes

    def pick(self, *args, **kwargs) -> list[VolInfo]:
        raise NotImplementedError("Subclasses must implement this method.")

class Downloader(SessionContext):

    def __init__(self, 
            dest_dir: str,
            book: BookInfo,
            volumes: list[VolInfo],
            callback: Optional[Callable[[VolInfo], None]] = None,
            retry_times: int = 3,
            *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._dest_dir: str = dest_dir
        self._book: BookInfo = book
        self._volumes: list[VolInfo] = volumes
        self._callback: Optional[Callable[[VolInfo], None]] = callback
        self._retry_times: int = retry_times

    def download(self):
        raise NotImplementedError("Subclasses must implement this method.")
