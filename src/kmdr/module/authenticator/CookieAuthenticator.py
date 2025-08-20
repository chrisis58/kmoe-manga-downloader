from typing import Optional

from kmdr.core import Authenticator, AUTHENTICATOR, LoginError

from .utils import check_status

@AUTHENTICATOR.register()
class CookieAuthenticator(Authenticator):
    def __init__(self, proxy: Optional[str] = None, *args, **kwargs):
        super().__init__(proxy, *args, **kwargs)

        if 'command' in kwargs and kwargs['command'] == 'status':
            self._show_quota = True
        else:
            self._show_quota = False

    def _authenticate(self) -> bool:
        cookie = self._configurer.cookie
        
        if not cookie:
            raise LoginError("No cookie found, please login first.", ['kmdr login -u <username>'])
        
        self._session.cookies.update(cookie)
        return check_status(
            self._session,
            show_quota=self._show_quota,
            is_vip_setter=lambda value: setattr(self._profile, 'is_vip', value),
            level_setter=lambda value: setattr(self._profile, 'user_level', value),
        )