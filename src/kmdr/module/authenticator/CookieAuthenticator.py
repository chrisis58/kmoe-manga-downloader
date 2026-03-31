from kmdr.core import AUTHENTICATOR, Authenticator, LoginError
from kmdr.core.console import emit
from kmdr.core.structure import Credential


@AUTHENTICATOR.register()
class CookieAuthenticator(Authenticator):
    def __init__(self, auto_save: bool = True, *args, **kwargs):
        super().__init__(auto_save=auto_save, *args, **kwargs)

        if "command" in kwargs and kwargs["command"] == "status":
            self._show_quota = self._console.is_interactive
        else:
            self._show_quota = False

    async def _authenticate(self) -> Credential:
        from .utils import check_status

        cookie = self._configurer.cookie

        if not cookie:
            raise LoginError("无法找到 Cookie，请先完成登录。", ["kmdr login -u <username>"])

        cred: Credential = await check_status(
            self._session,
            self._console,
            username=self._configurer.config.username or "__FROM_COOKIE__",
            cookies=cookie,
            show_quota=self._show_quota,
        )

        emit(cred)

        return cred
