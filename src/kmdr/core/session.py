from typing import Optional

from aiohttp import ClientSession

from .bases import SESSION_MANAGER, SessionManager
from .defaults import HEADERS

# 通常只会有一个 SessionManager 的实现
# 因此这里直接注册为默认实现
@SESSION_MANAGER.register()
class KmdrSessionManager(SessionManager):
    """
    Kmdr 的 HTTP 会话管理类，支持从参数中初始化 ClientSession 的实例。
    """

    def __init__(self, proxy: Optional[str] = None, *args, **kwargs):
        session = ClientSession(proxy=proxy, trust_env=True, headers=HEADERS)
        self._session = session

    def session(self) -> ClientSession:
        assert self._session is not None, "Session has not been initialized."
        return self._session