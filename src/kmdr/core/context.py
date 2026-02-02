from typing import Optional

from aiohttp import ClientSession
from rich.progress import Progress

from kmdr.core.pool import CredentialPool

from .defaults import (
    Configurer as InnerConfigurer,
    session_var,
    base_url_var,
    progress_definition,
)
from .console import _console

_lazy_progress: Optional[Progress] = None
_lazy_cred_pool: Optional[CredentialPool] = None


class TerminalContext:
    def __init__(self, *args, **kwargs):
        super().__init__()
        self._console = _console

    @property
    def _progress(self) -> Progress:
        global _lazy_progress
        if _lazy_progress is None:
            _lazy_progress = Progress(*progress_definition, console=self._console, refresh_per_second=4)
        return _lazy_progress


class ConfigContext:
    def __init__(self, *args, **kwargs):
        super().__init__()
        self._configurer = InnerConfigurer()


class SessionContext:
    def __init__(self, *args, **kwargs):
        super().__init__()

    @property
    def _session(self) -> ClientSession:
        return session_var.get()

    @_session.setter
    def _session(self, value: ClientSession):
        session_var.set(value)

    @property
    def _base_url(self) -> str:
        return base_url_var.get()

    @_base_url.setter
    def _base_url(self, value: str):
        base_url_var.set(value)


class CredentialPoolContext(ConfigContext):
    def __init__(self, *args, **kwargs):
        super().__init__()

    @property
    def _pool(self) -> CredentialPool:
        """全局懒加载的凭证池实例。"""
        global _lazy_cred_pool
        if _lazy_cred_pool is None:
            _lazy_cred_pool = CredentialPool(self._configurer)
        return _lazy_cred_pool

    def reset_pool(self) -> None:
        """清除凭证池缓存，下次访问时会重新加载凭证池状态。"""
        global _lazy_cred_pool
        _lazy_cred_pool = None
