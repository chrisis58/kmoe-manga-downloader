from typing import Optional

from kmdr.core.bases import PoolManager, POOL_MANAGER
from kmdr.core.console import info


@POOL_MANAGER.register(hasvalues={"pool_command": "update"})
class PoolCredUpdator(PoolManager):
    def __init__(self, username: str, note: Optional[str] = None, order: Optional[int] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._username = username
        self._note = note
        self._order = order

    async def operate(self) -> None:
        cred = self._pool.find(self._username)

        if not cred:
            info(f"凭证池中不存在用户 '{self._username}' 。")
            return

        if self._note is not None:
            cred.note = self._note

        if self._order is not None:
            cred.order = self._order

        self._configurer.update()
        info(f"已更新用户 '{self._username}' 的信息。")
