from typing import Optional
from urllib.parse import urlsplit, urljoin
from typing import Type
from types import TracebackType

import asyncio
from aiohttp import ClientSession

from .constants import BASE_URL, API_ROUTE
from .utils import async_retry, PrioritySorter, get_random_ua
from .bases import SESSION_MANAGER, SessionManager
from .defaults import TRUE_UA
from .error import InitializationError, RedirectError
from .protocol import Supplier
from .console import *
from .protocol import AsyncCtxManager



# 通常只会有一个 SessionManager 的实现
# 因此这里直接注册为默认实现
@SESSION_MANAGER.register()
class KmdrSessionManager(SessionManager):
    """
    Kmdr 的 HTTP 会话管理类，支持从参数中初始化 ClientSession 的实例。
    """

    def __init__(self, proxy: Optional[str] = None, book_url: Optional[str] = None, fake_ua: bool = False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._proxy = proxy
        self._headers = {
            'User-Agent': get_random_ua() if fake_ua else TRUE_UA
        }

        self._sorter = PrioritySorter[str]()
        [self._sorter.set(alt) for alt in BASE_URL.alternatives()]
        self._sorter.incr(BASE_URL.DEFAULT.value, 2)
        self._sorter.incr(self._base_url, 5)

        if book_url is not None and book_url.strip() != "" :
            splited = urlsplit(book_url)
            primary_base_url = f"{splited.scheme}://{splited.netloc}"
            debug("提升书籍链接所在镜像地址优先级:", primary_base_url)

            self._sorter.incr(primary_base_url, 10)
        debug("镜像地址优先级排序:", self._sorter)

    async def session(self) -> AsyncCtxManager[ClientSession]:
        try:
            if self._session is not None and not self._session.closed:
                # 幂等性检查：如果 session 已经存在且未关闭，直接返回
                return SessionCtxManager(self._session)
        except LookupError:
            # session_var 尚未设置
            pass

        with self._console.status("初始化中..."):
            
            self._base_url = await self._probing_base_url()
            # 持久化配置
            self._configurer.set_base_url(self._base_url)
            debug("使用的基础 URL:", self._base_url)
            debug("使用的代理:", self._proxy)

            self._session = ClientSession(
                base_url=self._base_url,
                proxy=self._proxy,
                trust_env=True,
                headers=self._headers,
            )

            return SessionCtxManager(self._session)
    
    async def validate_url(self, session: ClientSession, url_supplier: Supplier[str]) -> bool:
        try:
            async with session.head(
                # 这里只请求登录页面的头信息保证快速响应
                # 选择登录页面，一个是因为登录页面对所有用户都开放
                # 另外是因为不同网站的登录页面通常是不同的，可以有效区分不同的网站
                # 如果后续发现有更合适的探测方式，可以考虑替换
                urljoin(url_supplier(), API_ROUTE.LOGIN),
                allow_redirects=False
            ) as response:
                if response.status in (301, 302, 307, 308) and 'Location' in response.headers:
                    new_location = urlsplit(response.headers['Location'])
                    raise RedirectError("检测到重定向", new_base_url=f"{new_location.scheme}://{new_location.netloc}")

                return response.status == 200
        except Exception as e:
            info(f"[yellow]无法连接到镜像: {url_supplier()}，错误信息: {e}[/yellow]")
            return False

    async def _probing_base_url(self) -> str:
        """
        探测可用的镜像地址。
        顺序为：首选地址 -> 备用地址
        当前首选地址不可用时，尝试备用地址，直到找到可用的地址或耗尽所有选项。
        如果所有地址均不可用，则抛出 InitializationError 异常。

        :raises InitializationError: 如果所有镜像地址均不可用。
        :return: 可用的镜像地址。
        """

        ret_base_url: str
    
        def get_base_url() -> str:
            nonlocal ret_base_url
            return ret_base_url
        
        def set_base_url(value: str) -> None:
            nonlocal ret_base_url
            ret_base_url = value

        async with ClientSession(proxy=self._proxy, trust_env=True, headers=self._headers) as probe_session:
            # TODO: 请求远程仓库中的镜像列表，并添加到 sorter 中

            for bu in self._sorter.sort():
                set_base_url(bu)

                if await async_retry(
                    base_url_setter=set_base_url,
                    on_failure=lambda e: info(f"[yellow]无法连接到镜像: {get_base_url()}，错误信息: {e}[/yellow]"),
                )(self.validate_url)(probe_session, get_base_url):
                    return get_base_url()

            raise InitializationError(f"所有镜像均不可用，请检查您的网络连接或使用其他镜像。\n详情参考：https://github.com/chrisis58/kmoe-manga-downloader/blob/main/mirror/mirrors.json")

class SessionCtxManager:
    def __init__(self, session: ClientSession):
        self._session = session

    async def __aenter__(self) -> ClientSession:
        await self._session.__aenter__()
        return self._session

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType]
    ):
        await self._session.__aexit__(exc_type, exc_value, traceback)

        if exc_type in (KeyboardInterrupt, asyncio.CancelledError):
            debug("任务被取消，正在清理资源")
            await asyncio.sleep(0.01)
