from typing import Optional

from kmdr.core import Authenticator, AUTHENTICATOR

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
            print("No cookie found. Please login first.")
            return False
        
        self._session.cookies.update(cookie)
        return check_status(self._session, show_quota=self._show_quota)