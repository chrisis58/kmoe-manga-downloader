from typing import Optional, Callable

from aiohttp import ClientSession

from .utils import async_retry
from .bases import SESSION_MANAGER, SessionManager
from .defaults import HEADERS
from .error import InitializationError, RedirectError
from .protocol import Suppiler



# 通常只会有一个 SessionManager 的实现
# 因此这里直接注册为默认实现
@SESSION_MANAGER.register()
class KmdrSessionManager(SessionManager):
    """
    Kmdr 的 HTTP 会话管理类，支持从参数中初始化 ClientSession 的实例。
    """

    def __init__(self, proxy: Optional[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._proxy = proxy

    async def session(self) -> ClientSession:
        try:
            if self._session is not None and not self._session.closed:
                # 幂等性检查：如果 session 已经存在且未关闭，直接返回
                return self._session
        except LookupError:
            # session_var 尚未设置
            pass

        self._session = await self._probing_base_url()

        with self._console.status("初始化中..."):
            
            self._base_url = await self._probing_base_url()

            self._session = ClientSession(
                base_url=self._base_url,
                proxy=self._proxy,
                trust_env=True,
                headers=HEADERS,
            )

            return self._session
    
    async def validate_url(self, session: ClientSession, url_supplier: Suppiler[str]) -> bool:
        async with session.head(url_supplier(), allow_redirects=False) as response:
            if response.status in (301, 302, 307, 308) and 'Location' in response.headers:
                new_location = response.headers['Location']
                raise RedirectError("检测到重定向", new_base_url=new_location)

            return response.status == 200

    async def _probing_base_url(self) -> str:
        async with ClientSession(proxy=self._proxy, trust_env=True, headers=HEADERS) as probe_session:

            valid = await async_retry(
                base_url_setter=self._configurer.set_base_url
            )(self.validate_url)(probe_session, self._configurer.get_base_url)

            if valid:
                return self._configurer.base_url
            else:
                # TODO: 添加备用镜像的探测
                raise InitializationError(f"对应镜像无法连接: {self._configurer.base_url}。请检查您的网络连接或尝试使用其他镜像。",)
