import time
from typing import Iterator, Optional
import itertools

import asyncio

from .defaults import Configurer
from .structure import Credential, CredentialStatus, QuotaInfo
from .console import debug
from .utils import calc_reset_time

UNLIMITED_WORKERS = 99999
"""不限制并发下载数的标记值"""

class CredentialPool:
    def __init__(self, 
            config: Configurer,
    ):
        self._config = config
        self._cycle_iterator: Optional[Iterator[Credential]] = None
        self._active_count: int = 0

        self._pooled_map: dict[str, PooledCredential] = {}

    @property
    def pool(self) -> list[Credential]:
        """返回当前的凭证池列表"""
        return self._config.config.cred_pool or []

    def _refresh_iterator(self):
        active = self.active_creds
        debug("凭证池活跃账号数：", len(active))
        self._active_count = len(active)
        if active:
            self._cycle_iterator = itertools.cycle(active)
        else:
            self._cycle_iterator = None

    @property
    def active_count(self) -> int:
        if self._cycle_iterator is None:
            self._refresh_iterator()
        return self._active_count
    
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

    def update(self, cred: Credential) -> bool:
        """更新指定用户名的凭证信息"""
        if self._config.config.cred_pool is None:
            return False
        
        for idx, cre in enumerate(self._config.config.cred_pool):
            if cre.username == cred.username:
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

    def pooled_refresh_candidates(self, max_workers: int = UNLIMITED_WORKERS) -> list['PooledCredential']:
        return [self.get_pooled(candidate, max_workers) for candidate in self.refresh_candidates]        
    
    @property
    def refresh_candidates(self) -> list[Credential]:
        """
        返回所有需要更新额度信息的凭证列表。
        判定标准：
        1. 累计未同步流量超过 50MB
        2. 状态为配额耗尽(QUOTA_EXCEEDED) 且 上次更新时间早于最近一次重置日
        """
        candidates = []
        now_ts = time.time()

        for cred in self.pool:
            unsynced = cred.user_quota.unsynced_usage + (cred.vip_quota.unsynced_usage if cred.vip_quota else 0.0)

            if unsynced > 50.0:
                candidates.append(cred)
                continue

            if cred.status == CredentialStatus.QUOTA_EXCEEDED:
                if self.__should_refresh_quota(now_ts, cred.user_quota) \
                    or self.__should_refresh_quota(now_ts, cred.vip_quota):
                    # 如果有任何一项配额在上次更新时间后经过了重置日，则加入更新列表
                    candidates.append(cred)
                    continue

        return candidates
    
    def __should_refresh_quota(self, now_ts: float, quota: Optional[QuotaInfo]) -> bool:
        """判断指定的配额信息是否需要刷新"""
        if quota is None:
            return False
        if not quota.update_at:
            return True
        reset_timestamp = calc_reset_time(quota.reset_day, quota.update_at)
        return now_ts >= reset_timestamp

    def get_next(self, max_workers: int = UNLIMITED_WORKERS, max_recursion_depth: int = 3) -> Optional['PooledCredential']:
        """
        获取下一个可用的 PooledCredential 实例。
        
        :param max_workers: 每个凭证允许的最大并发下载数
        :param max_recursion_depth: 最大递归深度，防止无限递归，不建议修改
        :return: 下一个可用的 PooledCredential 实例，若无可用则返回 None
        """

        if max_recursion_depth <= 0:
            return None

        if self._cycle_iterator is None:
            self._refresh_iterator()

        if self._cycle_iterator is None:
            return None

        max_attempts = max(1, self._active_count)
        
        for _ in range(max_attempts):
            raw_cred = next(self._cycle_iterator)
            
            if raw_cred.status != CredentialStatus.ACTIVE:
                continue

            return self.get_pooled(raw_cred, max_workers)
        
        self._refresh_iterator()
        return self.get_next(max_workers, max_recursion_depth - 1)

    def get_pooled(self, cred: Credential, max_workers: int) -> 'PooledCredential':
        key = cred.username
        
        if key not in self._pooled_map:
            self._pooled_map[key] = PooledCredential(cred, max_workers)
            
        elif self._pooled_map[key].inner is not cred:
            self._pooled_map[key].update_cred(cred)

        return self._pooled_map[key]

class PooledCredential:
    def __init__(self, credential: Credential, max_workers: int = UNLIMITED_WORKERS):
        self._cred = credential
        
        self._cred.user_quota.reserved = 0.0
        if self._cred.vip_quota:
            self._cred.vip_quota.reserved = 0.0

        self.update_lock = asyncio.Lock()
        """用于更新凭证信息的异步锁,避免多个协程重复更新"""

        self.download_semaphore: asyncio.Semaphore = asyncio.Semaphore(max_workers)
        """用于限制当前凭证的并发下载数的信号量"""

    @property
    def inner(self) -> Credential:
        return self._cred
    
    @inner.setter
    def inner(self, cred: Credential):
        self._cred = cred

    def _get_target(self, is_vip: bool) -> Optional[QuotaInfo]:
        if is_vip and self._cred.vip_quota:
            return self._cred.vip_quota
        return self._cred.user_quota

    def update_cred(self, cred: Credential, force: bool = False):
        """
        更新内部的 Credential 信息
        
        :param cred: 新的 Credential 信息
        :param force: 是否强制更新所有信息，默认根据更新时间决定是否覆盖
        """
        if self._cred.username != '__FROM_COOKIE__' and cred.username != self._cred.username:
            raise ValueError("无法更新凭证：用户名不匹配。")

        self.__update_quota(cred.user_quota, self._cred.user_quota, force=force)
        
        if cred.vip_quota and self._cred.vip_quota:
            self.__update_quota(cred.vip_quota, self._cred.vip_quota, force=force)
        
        self._cred = cred

    def __update_quota(self, target: QuotaInfo, source: QuotaInfo, force: bool = False):
        target.reserved = source.reserved

        target.unsynced_usage = 0.0 if force else source.unsynced_usage

        if force or target.update_at >= source.update_at:
            return

        target.total = source.total
        target.used = source.used
        target.reset_day = source.reset_day
        target.update_at = source.update_at
        
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

    def is_recently_synced(self, is_vip: bool = True, cooldown: float = 30.0) -> bool:
        """检查是否最近刚刚同步过"""
        target = self._get_target(is_vip)
        if target:
            return (time.time() - target.update_at) < cooldown
        return False