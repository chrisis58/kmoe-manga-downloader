from typing import Optional
import re

from rich.prompt import Prompt

from kmdr.core import Authenticator, AUTHENTICATOR, LoginError

from .utils import check_status

CODE_OK = 'm100'

CODE_MAPPING = {
    'e400': "帳號或密碼錯誤。",
    'e401': "非法訪問，請使用瀏覽器正常打開本站",
    'e402': "帳號已經註銷。不會解釋原因，無需提問。",
    'e403': "驗證失效，請刷新頁面重新操作。",
}

@AUTHENTICATOR.register(
    hasvalues = {'command': 'login'}
)
class LoginAuthenticator(Authenticator):
    def __init__(self, username: str, proxy: Optional[str] = None, password: Optional[str] = None, show_quota = True, *args, **kwargs):
        super().__init__(proxy, *args, **kwargs)
        self._username = username
        self._show_quota = show_quota

        if password is None:
            password = Prompt.ask("请输入密码", password=True, console=self._console)

        self._password = password

    async def _authenticate(self) -> bool:

        async with self._session.post(
            url = 'https://kox.moe/login_do.php', 
            data = {
                'email': self._username,
                'passwd': self._password,
                'keepalive': 'on'
            },
        ) as response:

            response.raise_for_status()
            match = re.search(r'"\w+"', await response.text())

            if not match:
                raise LoginError("无法解析登录响应。")
            
            code = match.group(0).split('"')[1]
            if code != CODE_OK:
                raise LoginError(f"认证失败，错误代码：{code} " + CODE_MAPPING.get(code, "未知错误。"))

            if await check_status(self._session, show_quota=self._show_quota):
                cookie = self._session.cookie_jar.filter_cookies('https://kox.moe')
                self._configurer.cookie = {key: morsel.value for key, morsel in cookie.items()}

                return True
            
            return False
