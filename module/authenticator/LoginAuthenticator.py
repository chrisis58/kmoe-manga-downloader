from typing import Optional
import re

from core import Authenticator, AUTHENTICATOR

from .utils import check_status


@AUTHENTICATOR.register(
    hasvalues = {'command': 'login'}
)
class LoginAuthenticator(Authenticator):
    def __init__(self, username: str, proxy: Optional[str] = None, password: Optional[str] = None, show_quota = True, *args, **kwargs):
        super().__init__(proxy, *args, **kwargs)
        self._username = username
        self._show_quota = show_quota

        if password is None:
            password = input("please input your password: \n")

        self._password = password

    def _authenticate(self) -> bool:
        
        response = self._session.post(
            url = 'https://kox.moe/login_do.php', 
            data = {
                'email': self._username,
                'passwd': self._password,
                'keepalive': 'on'
            },
        )
        response.raise_for_status()
        
        match = re.search('"\w+"', response.text)
        if not match:
            raise RuntimeError("Failed to extract authentication code from response.")
        code = match.group(0).split('"')[1]
        if code != 'm100':
            if code == 'e400':
                print("帳號或密碼錯誤。")
            elif code == 'e401':
                print("非法訪問，請使用瀏覽器正常打開本站")
            elif code == 'e402':
                print("帳號已經註銷。不會解釋原因，無需提問。")
            elif code == 'e403':
                print("驗證失效，請刷新頁面重新操作。")
            raise RuntimeError("Authentication failed with code: " + code)
        
        if check_status(self._session, show_quota=self._show_quota):
            self._configurer.config.cookie = self._session.cookies.get_dict()
            self._configurer.update()
            return True
        
        return False
