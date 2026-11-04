import asyncio
from dataclasses import replace

from aiohttp import ClientError

from kmdr.core import AUTHENTICATOR, Authenticator, LoginError
from kmdr.core.console import emit, info, is_interactive
from kmdr.core.error import HtmlResolveError
from kmdr.core.structure import Credential, CredentialStatus, QuotaInfo


@AUTHENTICATOR.register()
class CookieAuthenticator(Authenticator):
    def __init__(self, auto_save: bool = True, *args, **kwargs):
        super().__init__(*args, auto_save=auto_save, **kwargs)
        self._for_download = kwargs.get("command") == "download"

        if "command" in kwargs and kwargs["command"] == "status":
            self._show_quota = is_interactive()
        else:
            self._show_quota = False

    async def _authenticate(self) -> Credential:
        from .utils import check_status

        cookie = self._configurer.cookie

        if not cookie:
            raise LoginError("无法找到 Cookie，请先完成登录。", ["kmdr login -u <username>"])

        username = self._configurer.config.username or "__FROM_COOKIE__"
        try:
            cred = await check_status(
                self._session,
                self._console,
                username=username,
                cookies=cookie,
                show_quota=self._show_quota,
            )
        except (ClientError, asyncio.TimeoutError, HtmlResolveError) as e:
            if not self._for_download:
                raise
            info(f"[yellow]账号状态查询失败，将使用已有 Cookie 继续尝试下载：{e}[/yellow]")
            cached = next((c for c in self._configurer.config.cred_pool or [] if c.username == username), None)
            if cached is not None:
                cred = replace(cached, cookies=cookie, quota_known=False, status=CredentialStatus.ACTIVE)
            else:
                cred = Credential(username=username, cookies=cookie, user_quota=QuotaInfo(1, 0.0, 0.0), level=0, quota_known=False)

        emit(cred)

        return cred
