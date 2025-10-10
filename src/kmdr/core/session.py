from typing import Optional
from urllib.parse import urlsplit

from aiohttp import ClientSession

from .constants import BASE_URL
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

    def __init__(self, proxy: Optional[str] = None, book_url: Optional[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._proxy = proxy

        # TODO: 可以从远程仓库获取最新的镜像列表，当前为硬编码
        self._alternatives = BASE_URL.alternatives()

        if book_url is not None and book_url.strip() != "" :
            # 从书籍 URL 中提取地址，优先级最高
            # self._base_url 是在 Configurer 中初始化的，默认为 BASE_URL.DEFAULT
            # 或者是用户手动配置的值
            splited = urlsplit(book_url)
            primary_base_url = f"{splited.scheme}://{splited.netloc}"

            if primary_base_url != self._base_url:
                # 如果从书籍 URL 中提取的地址与当前 base_url 不同，则将其作为首选地址
                # 并将当前 base_url 添加到备用地址列表中
                self._alternatives.add(self._base_url)
                self._base_url = primary_base_url
        
        if self._base_url != BASE_URL.DEFAULT.value:
            # 如果当前 base_url 不是默认值，则将默认值添加到备用地址列表中
            self._alternatives.add(BASE_URL.DEFAULT.value)

    async def session(self) -> ClientSession:
        try:
            if self._session is not None and not self._session.closed:
                # 幂等性检查：如果 session 已经存在且未关闭，直接返回
                return self._session
        except LookupError:
            # session_var 尚未设置
            pass

        with self._console.status("初始化中..."):
            
            self._base_url = await self._probing_base_url()
            # 持久化配置
            self._configurer.set_base_url(self._base_url)

            self._session = ClientSession(
                base_url=self._base_url,
                proxy=self._proxy,
                trust_env=True,
                headers=HEADERS,
            )

            return self._session
    
    async def validate_url(self, session: ClientSession, url_supplier: Suppiler[str]) -> bool:
        try:
            async with session.head(url_supplier(), allow_redirects=False) as response:
                if response.status in (301, 302, 307, 308) and 'Location' in response.headers:
                    new_location = response.headers['Location']
                    raise RedirectError("检测到重定向", new_base_url=new_location)

                return response.status == 200
        except Exception as e:
            self._console.print(f"[yellow]无法连接到镜像: {url_supplier()}，错误信息: {e}[/yellow]")
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
    
        def get_base_url() -> str:
            return self._base_url
        
        def set_base_url(value: str) -> None:
            self._base_url = value

        async with ClientSession(proxy=self._proxy, trust_env=True, headers=HEADERS) as probe_session:
            if await async_retry(
                base_url_setter=set_base_url,
                on_failure=lambda e: self._console.print(f"[yellow]无法连接到镜像: {get_base_url()}，错误信息: {e}[/yellow]"),
            )(self.validate_url)(probe_session, get_base_url):
                # 首选地址可用，直接返回
                return get_base_url()

            for bu in self._alternatives:
                # 尝试备用地址
                set_base_url(bu)
                if await async_retry(
                    base_url_setter=set_base_url,
                )(self.validate_url)(probe_session, get_base_url):
                    return get_base_url()

            raise InitializationError(f"所有镜像均不可用，请检查您的网络连接或使用其他镜像。\n详情参考：https://github.com/chrisis58/kmoe-manga-downloader/blob/main/mirror/mirrors.json",)

