from collections import defaultdict
import time
from typing import Iterator, Optional
import itertools
from contextlib import contextmanager

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
        self._rr_counters: Optional[defaultdict[int, int]] = None
        self._tiered_groups: Optional[defaultdict[int, list[Credential]]] = None

    @property
    def pool(self) -> list[Credential]:
        """返回当前的凭证池列表"""
        return self._config.config.cred_pool or []

    @property
    def active_count(self) -> int:
        return len(self.active_creds)

    def dump(self) -> None:
        """保存当前凭证池到配置文件"""
        self._config.update()


    
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
        self.evict_iterator_cache()

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
                self.evict_iterator_cache(cred.username)
                return True
        return False

    def clear(self) -> None:
        """清空凭证池中的所有凭证"""
        self._config.config.cred_pool = []
        self._config.update()
        self.evict_iterator_cache()

    @property
    def active_creds(self) -> list[Credential]:
        """返回所有状态为 ACTIVE 的凭证"""
        return [cred for cred in self.pool if cred.status == CredentialStatus.ACTIVE]

    def pooled_refresh_candidates(self, max_workers: int = UNLIMITED_WORKERS) -> list['PooledCredential']:
        return [self.get_pooled(candidate, max_workers) for candidate in self.refresh_candidates]        

    @property
    def refresh_candidates(self) -> list[Credential]:
        """
        返回所有需要更新额度信息的凭证列表。
        判定标准：
        1. 超过 3 天未同步
        2. 累计未同步流量超过 50MB
        3. 状态为配额耗尽(QUOTA_EXCEEDED) 且 上次更新时间早于最近一次重置日
        """
        candidates = []
        now_ts = time.time()

        for cred in self.pool:
            if cred.status == CredentialStatus.DISABLED:
                continue

            if cred.user_quota.update_at < time.time() - 3 * 3600 * 24:
                candidates.append(cred)
                continue

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

    def get_pooled(self, cred: Credential, max_workers: int) -> 'PooledCredential':
        key = cred.username

        if key not in self._pooled_map:
            self._pooled_map[key] = PooledCredential(cred, max_workers)

        elif self._pooled_map[key].inner is not cred:
            self._pooled_map[key].update_cred(cred)

        return self._pooled_map[key]
    
    def evict_iterator_cache(self, username: Optional[str] = None) -> None:
        """清除轮询迭代器的缓存，强制在下一次获取时刷新"""
        self._tiered_groups = None
        self._rr_counters = None
        if username:
            self._pooled_map.pop(username, None)
    
    def get_tiered_candidates(self, preferred_cred: Optional[Credential] = None, max_workers: int = UNLIMITED_WORKERS) -> Iterator['PooledCredential']:
        """
        生成一个分层级的候选凭证迭代器。
        逻辑：
        1. 优先返回指定的 preferred_cred (粘滞会话)。
        2. 然后按 Order 从小到大遍历。
        3. 同一个 Order 内，使用 Round-Robin (轮转) 顺序返回。
        """

        if self._rr_counters is None:
            # lazy init
            self._rr_counters = defaultdict(int)

        active_creds = [cred for cred in self.pool if cred.status == CredentialStatus.ACTIVE]

        if not active_creds:
            return

        # 按 Order 分组
        if self._tiered_groups is None:
            self._tiered_groups = defaultdict(list)
            for p_cred in active_creds:
                self._tiered_groups[p_cred.order].append(p_cred)
        tiered_groups = self._tiered_groups
        sorted_orders = sorted(tiered_groups.keys())

        # 粘滞优先
        skipped_username = None
        if preferred_cred:
            pooled_cred = self.get_pooled(preferred_cred, max_workers)
            if pooled_cred.status == CredentialStatus.ACTIVE:
                yield pooled_cred
                skipped_username = preferred_cred.username

        # 分层轮询
        for order in sorted_orders:
            group = tiered_groups[order]
            
            start_index = self._rr_counters[order] % len(group)
            self._rr_counters[order] += 1

            for i in range(len(group)):
                # left rotate
                index = (i + start_index) % len(group)
                if skipped_username and group[index].username == skipped_username:
                    continue
                pooled_cred = self.get_pooled(group[index], max_workers)
                if pooled_cred.status == CredentialStatus.ACTIVE:
                    yield pooled_cred

_handle_counter = itertools.count(1)
"""全局的预留句柄生成器"""

class PooledCredential:
    def __init__(self, credential: Credential, max_workers: int = UNLIMITED_WORKERS):
        self._cred = credential
        
        self._reserved_map: dict[int, float] = {}
        self._reserved: float = 0.0

        self._max_workers = max_workers
        self._update_lock = None
        self._download_semaphore = None

    @property
    def update_lock(self) -> asyncio.Lock:
        """用于更新凭证信息的异步锁,避免多个协程重复更新"""
        if self._update_lock is None:
            self._update_lock = asyncio.Lock()
        return self._update_lock
    
    @property
    def download_semaphore(self) -> asyncio.Semaphore:
        """用于限制当前凭证的并发下载数的信号量"""
        if self._download_semaphore is None:
            self._download_semaphore = asyncio.Semaphore(self._max_workers)
        return self._download_semaphore

    @property
    def inner(self) -> Credential:
        return self._cred

    @property
    def username(self) -> str:
        return self._cred.username

    @property
    def quota_remaining(self) -> float:
        return self._cred.quota_remaining - self._reserved
    
    @property
    def cookies(self) -> dict[str, str]:
        return self._cred.cookies

    @property
    def reserved(self) -> float:
        return self._reserved

    @property
    def status(self) -> CredentialStatus:
        return self._cred.status
    
    @status.setter
    def status(self, value: CredentialStatus):
        self._cred.status = value

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

        self._cred.cookies = cred.cookies
        self._cred.status = cred.status
        self._cred.level = cred.level
        self._cred.nickname = cred.nickname

        if force or cred.user_quota.update_at >= self._cred.user_quota.update_at:
            self._cred.user_quota = cred.user_quota

        if self._cred.vip_quota and cred.vip_quota:
             if force or cred.vip_quota.update_at >= self._cred.vip_quota.update_at:
                self._cred.vip_quota = cred.vip_quota

    def reserve(self, size_mb: float) -> Optional[int]:
        """预留指定大小的额度，成功返回句柄，失败返回 None"""
        if self.quota_remaining >= size_mb:
            handle = _handle_counter.__next__()
            self._reserved_map[handle] = size_mb
            self._reserved += size_mb
            return handle
        return None

    def commit(self, handle: Optional[int], is_vip: bool = True):
        if handle is None:
            return
        reserved_amount = self._reserved_map.pop(handle, None)
        
        if reserved_amount is None:
            return

        target = self._get_target(is_vip)
        if target:
            self._reserved = max(0.0, self._reserved - reserved_amount)
            target.unsynced_usage += reserved_amount
            target.update_at = time.time()

    def rollback(self, handle: Optional[int]):
        if handle is None:
            return
        reserved_amount = self._reserved_map.pop(handle, None)

        if reserved_amount is not None:
            self._reserved = max(0.0, self._reserved - reserved_amount)

    def is_recently_synced(self, is_vip: bool = True, cooldown: float = 10.0) -> bool:
        """检查是否最近刚刚同步过"""
        target = self._get_target(is_vip)
        if target:
            return (time.time() - target.update_at) < cooldown
        return False

    @contextmanager
    def quota_transaction(self, size: float, is_vip: bool = True):
        """
        额度预留的上下文管理器。
        Yields:
            def finalize(success: bool): 用于在业务完成时手动提交或回滚的回调函数。
            如果预留失败，yield None。
        """
        handle = self.reserve(size)
        
        if handle is None:
            yield None
            return

        is_finalized = False

        def finalize(success: bool):
            nonlocal is_finalized
            is_finalized = True
            if success:
                self.commit(handle, is_vip=is_vip)
            else:
                self.rollback(handle)

        try:
            yield finalize

        except Exception:
            if not is_finalized:
                self.rollback(handle)
                is_finalized = True
            raise

        finally:
            if not is_finalized:
                self.rollback(handle)