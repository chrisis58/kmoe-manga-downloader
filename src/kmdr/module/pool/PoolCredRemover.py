from kmdr.core.bases import PoolManager, POOL_MANAGER
from kmdr.core.console import info

@POOL_MANAGER.register(
    hasvalues={'pool_command': 'remove'}
)
class PoolCredRemover(PoolManager):
    
    def __init__(self, username: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._username = username

    async def operate(self) -> None:
        ret = self._pool.remove(self._username)
        if not ret:
            info(f"凭证池中不存在用户 '{self._username}' 。")
        else:
            info(f"已从凭证池中移除用户 '{self._username}' 。")
