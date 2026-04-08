from kmdr.core.bases import POOL_MANAGER, PoolManager
from kmdr.core.console import emit, info


@POOL_MANAGER.register(hasvalues={"pool_command": "remove"})
class PoolCredRemover(PoolManager):
    def __init__(self, username: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._username = username

    async def operate(self) -> None:
        ret = self._pool.remove(self._username)
        if not ret:
            info(f"凭证池中不存在用户 '{self._username}' 。")
            emit(f"凭证池中不存在用户 '{self._username}' 。")
        else:
            emit(username=self._username)
            info(f"已从凭证池中移除用户 '{self._username}' 。")
