import time
from typing import Iterator, Optional
import itertools

from .defaults import Configurer
from .structure import Credential, CredentialStatus, QuotaInfo

class CredentialPool:
    def __init__(self, config: Configurer):
        self._config = config
        self._cycle_iterator: Optional[Iterator[Credential]] = None

    @property
    def pool(self) -> list[Credential]:
        """返回当前的凭证池列表"""
        return self._config.config.cred_pool or []

    def _refresh_iterator(self):
        active = self.active_creds
        if active:
            self._cycle_iterator = itertools.cycle(active)
        else:
            self._cycle_iterator = None
    
    def find(self, username: str) -> Optional[Credential]:
        """根据用户名查找对应的凭证"""
        for cred in self.pool:
            if cred.username == username:
                return cred
        return None

    def add(self, cred: Credential) -> None:
        """向凭证池中添加新的凭证"""
        if self._config.config.cred_pool is None:
            self._config.config.cred_pool = []
        
        self._config.config.cred_pool.append(cred)
        self._config.update()
        self._refresh_iterator()

    def check_duplicate(self, username: str) -> bool:
        """检查凭证池中是否已存在指定用户名的凭证"""
        for cred in self.pool:
            if cred.username == username:
                return True
        return False

    def remove(self, username: str) -> bool:
        """从凭证池中移除指定用户名的凭证"""
        if self._config.config.cred_pool is None:
            return False
        
        for cred in self._config.config.cred_pool:
            if cred.username == username:
                self._config.config.cred_pool.remove(cred)
                self._config.update()
                self._refresh_iterator()
                return True
        return False

    def update(self, username: str, cred: Credential) -> bool:
        """更新指定用户名的凭证信息"""
        if self._config.config.cred_pool is None:
            return False
        
        for idx, cre in enumerate(self._config.config.cred_pool):
            if cre.username == username:
                self._config.config.cred_pool[idx] = cred
                self._config.update()
                self._refresh_iterator()
                return True
        return False

    def update_status(self, username: str, status: CredentialStatus) -> bool:
        """更新指定用户名的凭证状态"""
        if self._config.config.cred_pool is None:
            return False
        
        for cred in self._config.config.cred_pool:
            if cred.username == username:
                if cred.status != status:
                    cred.status = status
                    self._config.update()
                    self._refresh_iterator()
                return True
        return False

    def clear(self) -> None:
        """清空凭证池中的所有凭证"""
        self._config.config.cred_pool = []
        self._config.update()
        self._refresh_iterator()

    @property
    def active_creds(self) -> list[Credential]:
        """返回所有状态为 ACTIVE 的凭证，按优先级排序"""
        creds = [cred for cred in self.pool if cred.status == CredentialStatus.ACTIVE]
        return sorted(creds, key=lambda x: x.order)

    def get_next(self, max_recursion_depth: int = 3) -> Optional[Credential]:
        if (max_recursion_depth <= 0):
            return None

        if self._cycle_iterator is None:
            self._refresh_iterator()

        if self._cycle_iterator is None:
            return None

        max_attempts = len(self.active_creds) 
        
        for _ in range(max_attempts):
            try:
                cred = next(self._cycle_iterator)
                if cred.status == CredentialStatus.ACTIVE:
                    return cred
            except StopIteration:
                self._refresh_iterator()
                return None
        
        self._refresh_iterator()
        return self.get_next(max_recursion_depth - 1)

class PooledCredential:
    def __init__(self, credential: Credential):
        self._cred = credential
        
        self._cred.user_quota.reserved = 0.0
        if self._cred.vip_quota:
            self._cred.vip_quota.reserved = 0.0

    @property
    def inner(self) -> Credential:
        return self._cred

    def _get_target(self, is_vip: bool) -> Optional[QuotaInfo]:
        if is_vip and self._cred.vip_quota:
            return self._cred.vip_quota
        return self._cred.user_quota

    def update_from_server(self, server_cred: Credential):
        if server_cred.username != self._cred.username:
            raise ValueError("无法更新凭证：用户名不匹配。")

        self._cred.level = server_cred.level
        self._cred.nickname = server_cred.nickname
        self._cred.cookies = server_cred.cookies

        self._overwrite_quota(self._cred.user_quota, server_cred.user_quota)
        
        if server_cred.vip_quota:
            if self._cred.vip_quota:
                self._overwrite_quota(self._cred.vip_quota, server_cred.vip_quota)
            else:
                self._cred.vip_quota = server_cred.vip_quota
        else:
            self._cred.vip_quota = None

    def _overwrite_quota(self, local: QuotaInfo, remote: QuotaInfo):
        local.total = remote.total
        local.used = remote.used
        local.reset_day = remote.reset_day
        local.update_at = time.time()
        
        local.unsynced_usage = 0.0
        

    def reserve(self, size_mb: float, is_vip: bool = True) -> bool:
        target = self._get_target(is_vip)
        if target and target.remaining >= size_mb:
            target.reserved += size_mb
            return True
        return False

    def commit(self, size_mb: float, is_vip: bool = True):
        target = self._get_target(is_vip)
        if target:
            target.reserved = max(0.0, target.reserved - size_mb)
            
            target.unsynced_usage += size_mb 
            
            target.update_at = time.time()

    def rollback(self, size_mb: float, is_vip: bool = True):
        target = self._get_target(is_vip)
        if target:
            target.reserved = max(0.0, target.reserved - size_mb)
