from typing import Optional

from aiohttp import ClientSession

from .bases import KMDR_SESSION
from .defaults import session_var, HEADERS

@KMDR_SESSION.register()
class KmdrSession(ClientSession):
    """
    Kmdr 的 HTTP 会话管理类，支持从参数中初始化。简化 ClientSession 的使用。
    """

    def __init__(self, proxy: Optional[str] = None, *args, **kwargs):
        ClientSession.__init__(self, proxy=proxy, trust_env=True, headers=HEADERS)
        session_var.set(self)