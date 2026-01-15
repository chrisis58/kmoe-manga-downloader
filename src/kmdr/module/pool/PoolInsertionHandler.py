from typing import Optional

from kmdr.core.bases import PoolManager, POOL_MANAGER
from kmdr.core.session import KmdrSessionManager
from kmdr.core.console import info

from kmdr.module.authenticator.LoginAuthenticator import LoginAuthenticator


@POOL_MANAGER.register(
    hasvalues={'pool_command': 'add'}
)
class PoolInsertionHandler(PoolManager):

    def __init__(self, username: str, password: Optional[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._username = username
        self._password = password

    async def operate(self) -> None:
        
        async with (await KmdrSessionManager().session()):
            authenticator = LoginAuthenticator(
                username=self._username,
                password=self._password,
                show_quota=False,
            )
            cred = await authenticator.authenticate()
            self._pool.add(cred)

            info(f"已将用户 '{self._username}' 添加到凭证池中。")
