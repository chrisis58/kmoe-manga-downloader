from kmdr.core.bases import PoolManager, POOL_MANAGER
from kmdr.core.console import info

@POOL_MANAGER.register(
    hasvalues={'pool_command': 'use'}
)
class PoolCredSwitcher(PoolManager):
    
    def __init__(self, username: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._username = username

    async def operate(self) -> None:

        cred = self._pool.find(self._username)

        if not cred:
            info(f"凭证池中不存在用户 '{self._username}' 。")
            return

        try:
            self._configurer.cookie = cred.cookies
        except Exception as e:
            info(f"[red]设置默认账号失败: {e}[/red]")
            return
        info(f"已将用户 '{self._username}' 应用为当前默认账号。")