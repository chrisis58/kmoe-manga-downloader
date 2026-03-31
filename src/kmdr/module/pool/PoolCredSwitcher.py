from kmdr.core.bases import POOL_MANAGER, PoolManager
from kmdr.core.console import emit, info


@POOL_MANAGER.register(hasvalues={"pool_command": "use"})
class PoolCredSwitcher(PoolManager):
    def __init__(self, username: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._username = username

    async def operate(self) -> None:
        cred = self._pool.find(self._username)

        if not cred:
            info(f"凭证池中不存在用户 '{self._username}' 。")
            emit(f"凭证池中不存在用户 '{self._username}' 。")
            return

        try:
            self._configurer.config.cookie = cred.cookies
            self._configurer.config.username = cred.username
            self._configurer.update()
            emit(username=self._username)
        except Exception as e:
            info(f"[red]设置默认账号失败: {e}[/red]")
            emit(e)
            return
        info(f"已将用户 '{self._username}' 应用为当前默认账号。")
