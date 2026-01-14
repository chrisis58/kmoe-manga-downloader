from typing import Optional
import re

from rich.prompt import Prompt

from kmdr.core import Authenticator, AUTHENTICATOR, LoginError
from kmdr.core.constants import API_ROUTE, LoginResponse
from kmdr.core.structure import Credential
from kmdr.core.utils import extract_cookies

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
            password = Prompt.ask("请输入密码", password=True, console=self._console)

        self._password = password

    async def _authenticate(self) -> Credential:

        async with self._session.post(
            url = API_ROUTE.LOGIN_DO,
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

            login_response = LoginResponse.from_code(code)
            if not LoginResponse.ok(login_response):
                raise LoginError(f"认证失败，错误代码：{login_response.name} {login_response.value}" )
            
            cookies = extract_cookies(response)

            cred: Credential = await check_status(
                self._session,
                self._console,
                self._username,
                cookies=cookies,
                show_quota=self._show_quota
            )
            self._credential = cred
            self._configurer.cookie = cred.cookies
            return cred