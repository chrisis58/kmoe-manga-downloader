from typing import Optional

from kmdr.core import Authenticator, AUTHENTICATOR, LoginError
from kmdr.core.structure import Credential

from .utils import check_status

@AUTHENTICATOR.register()
class CookieAuthenticator(Authenticator):
    def __init__(self, proxy: Optional[str] = None, *args, **kwargs):
        super().__init__(proxy, *args, **kwargs)

        if 'command' in kwargs and kwargs['command'] == 'status':
            self._show_quota = True
        else:
            self._show_quota = False

    async def _authenticate(self) -> Credential:
        cookie = self._configurer.cookie
        
        if not cookie:
            raise LoginError("无法找到 Cookie，请先完成登录。", ['kmdr login -u <username>'])

        cred: Credential = await check_status(
            self._session,
            self._console,
            username='__FROM_COOKIE__',
            cookies=cookie,
            show_quota=self._show_quota,
        )
        self._credential = cred
        return cred
