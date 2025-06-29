from core import Authenticator, AUTHENTICATOR

from .utils import check_status

@AUTHENTICATOR.register()
class CookieAuthenticator(Authenticator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if 'command' in kwargs and kwargs['command'] == 'status':
            self._show_quota = True
        else:
            self._show_quota = False

    def authenticate(self) -> bool:
        cookie = self._configurer.config.cookie
        
        self._session.cookies.update(cookie)
        return check_status(self._session, show_quota=self._show_quota)