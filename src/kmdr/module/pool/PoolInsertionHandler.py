from typing import Optional

from kmdr.core.bases import PoolManager, POOL_MANAGER
from kmdr.core.session import KmdrSessionManager
from kmdr.core.console import info

from kmdr.module.authenticator.LoginAuthenticator import LoginAuthenticator


@POOL_MANAGER.register(hasvalues={"pool_command": "add"})
class PoolInsertionHandler(PoolManager):
    def __init__(self, username: str, password: Optional[str] = None, order: Optional[int] = None, note: Optional[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._username = username
        self._password = password
        self._order = order
        self._note = note

    async def operate(self) -> None:
        if self._pool.check_duplicate(self._username):
            info(f"用户 '{self._username}' 已存在于凭证池中。")
            return

        async with await KmdrSessionManager().session():
            authenticator = LoginAuthenticator(
                username=self._username,
                password=self._password,
                show_quota=False,
                auto_save=False,
            )
            cred = await authenticator.authenticate()

            if self._order is not None:
                cred.order = self._order
            if self._note is not None:
                cred.note = self._note

            self._pool.add(cred)

            info(f"已将用户 '{self._username}' 添加到凭证池中。")
