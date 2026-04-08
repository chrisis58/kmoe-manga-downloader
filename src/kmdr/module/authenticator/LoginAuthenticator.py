import re
from typing import Optional

from rich.prompt import Prompt

from kmdr.core import AUTHENTICATOR, Authenticator, LoginError
from kmdr.core.console import emit, is_interactive
from kmdr.core.constants import API_ROUTE, LoginResponse
from kmdr.core.error import NotInteractableError
from kmdr.core.structure import Credential
from kmdr.core.utils import extract_cookies


@AUTHENTICATOR.register(hasvalues={"command": "login"})
class LoginAuthenticator(Authenticator):
    def __init__(
        self,
        username: str,
        password: Optional[str] = None,
        show_quota=True,
        auto_save: bool = True,
        *args,
        **kwargs,
    ):
        super().__init__(auto_save=auto_save, *args, **kwargs)
        self._username = username
        self._show_quota = show_quota

        if password is None:
            if not is_interactive():
                raise NotInteractableError("无法获取密码，请通过 -p 命令行参数提供密码。")
            password = Prompt.ask("请输入密码", password=True, console=self._console)

        self._password = password

    async def _authenticate(self) -> Credential:
        from .utils import check_status

        async with self._session.post(
            url=API_ROUTE.LOGIN_DO,
            data={"email": self._username, "passwd": self._password, "keepalive": "on"},
        ) as response:
            response.raise_for_status()

            match = re.search(r'"\w+"', await response.text())

            if not match:
                raise LoginError("无法解析登录响应。")

            code = match.group(0).split('"')[1]

            login_response = LoginResponse.from_code(code)
            if not LoginResponse.ok(login_response):
                raise LoginError(f"认证失败，错误代码：{login_response.name} {login_response.value}")

            cookies = extract_cookies(response)

            cred: Credential = await check_status(
                self._session,
                self._console,
                self._username,
                cookies=cookies,
                show_quota=self._show_quota,
            )
            emit(cred)

            return cred
