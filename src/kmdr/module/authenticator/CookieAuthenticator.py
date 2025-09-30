from typing import Optional

from yarl import URL

from kmdr.core import Authenticator, AUTHENTICATOR, LoginError

from .utils import check_status, extract_base_url

@AUTHENTICATOR.register()
class CookieAuthenticator(Authenticator):
    def __init__(self, proxy: Optional[str] = None, book_url: Optional[str] = None, *args, **kwargs):
        super().__init__(proxy, *args, **kwargs)

        if 'command' in kwargs and kwargs['command'] == 'status':
            self._show_quota = True
        else:
            self._show_quota = False

        # 根据用户提供的 book_url 来决定访问的镜像站
        self._inner_base_url = extract_base_url(book_url, default=self._base_url)

    async def _authenticate(self) -> bool:
        cookie = self._configurer.cookie
        
        if not cookie:
            raise LoginError("无法找到 Cookie，请先完成登录。", ['kmdr login -u <username>'])
        
        self._session.cookie_jar.update_cookies(cookie, response_url=URL(self.base_url))
        return await check_status(
            self._session,
            self._console,
            base_url=self.base_url,
            show_quota=self._show_quota,
            is_vip_setter=lambda value: setattr(self._profile, 'is_vip', value),
            level_setter=lambda value: setattr(self._profile, 'user_level', value),
        )
