from typing import Optional
import re

from core import Authenticator, AUTHENTICATOR

from .utils import check_status


@AUTHENTICATOR.register(
    hasvalues = {'command': 'login'}
)
class LoginAuthenticator(Authenticator):
    def __init__(self, username: str, password: Optional[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._username = username

        if password is None:
            password = input("please input your password: \n")

        self._password = password

    def authenticate(self) -> bool:
        
        response = self._session.post(
            url = 'https://kox.moe/login_do.php', 
            data = {
                'email': self._username,
                'passwd': self._password,
                'keepalive': 'on'
            },
        )
        response.raise_for_status()
        
        code = re.search('"\w+"', response.text).group(0).split('"')[1]
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
        
        if check_status(self._session, show_quota=True):
            self._configurer.config.cookie = self._session.cookies.get_dict()
            self._configurer.update()
            return True
        
        return False
