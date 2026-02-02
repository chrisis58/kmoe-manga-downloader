import time
import unittest
from unittest.mock import Mock

from kmdr.core.pool import CredentialPool
from kmdr.core.structure import Credential, CredentialStatus, QuotaInfo


class MockConfigurer:
    """模拟配置管理器"""

    def __init__(self, cred_pool):
        self.config = Mock()
        self.config.cred_pool = cred_pool

    def update(self):
        pass


def create_pool(creds):
    config = MockConfigurer(creds)
    return CredentialPool(config)  # type: ignore


def create_quota(total=100.0, used=10.0):
    return QuotaInfo(total=total, used=used, reset_day=1, update_at=time.time())


def create_cred(username="user1", order=0, status=CredentialStatus.ACTIVE, is_vip=False):
    vip_quota = create_quota(500.0, 0.0) if is_vip else None
    return Credential(
        username=username,
        cookies={"token": "abc"},
        user_quota=create_quota(),
        vip_quota=vip_quota,
        level=1,
        order=order,
        status=status,
        nickname=f"Nick-{username}",
    )


class CredPoolScheduleTest (unittest.TestCase):
    def test_scheduling_basic_round_robin(self):
        """测试基本的同级轮询 (RR)"""
        # 准备三个同级账号
        c1 = create_cred("user1", order=1)
        c2 = create_cred("user2", order=1)
        c3 = create_cred("user3", order=1)

        pool = create_pool([c1, c2, c3])

        # 第一次获取迭代器
        candidates_1 = list(pool.get_tiered_candidates())
        assert len(candidates_1) == 3
        # 顺序可能是 [c1, c2, c3] (取决于列表顺序)
        assert candidates_1[0].inner.username == "user1"

        # 第二次获取迭代器 (应该发生了轮转)
        # 期望顺序: [c2, c3, c1]
        candidates_2 = list(pool.get_tiered_candidates())
        assert candidates_2[0].inner.username == "user2"
        assert candidates_2[-1].inner.username == "user1"

        # 第三次获取迭代器
        # 期望顺序: [c3, c1, c2]
        candidates_3 = list(pool.get_tiered_candidates())
        assert candidates_3[0].inner.username == "user3"

    def test_scheduling_tiered_priority(self):
        """测试分层优先级 (Order 0 优于 Order 1)"""
        # VIP (Order 0) 和 普通用户 (Order 1)
        vip1 = create_cred("vip1", order=0)
        vip2 = create_cred("vip2", order=0)
        norm1 = create_cred("norm1", order=1)

        pool = create_pool([norm1, vip1, vip2])

        # 获取迭代器
        candidates = list(pool.get_tiered_candidates())

        # 验证：VIP 必须排在前面
        assert len(candidates) == 3
        assert candidates[0].inner.order == 0
        assert candidates[1].inner.order == 0
        assert candidates[2].inner.order == 1

        # 验证：VIP 内部会轮转，但永远在 Normal 前面
        next_candidates = list(pool.get_tiered_candidates())
        assert next_candidates[0].inner.order == 0
        assert next_candidates[0].inner.username != candidates[0].inner.username  # VIP 内部轮转了
        assert next_candidates[2].inner.order == 1  # Normal 依然在最后

    def test_scheduling_sticky_session(self):
        """测试粘滞会话 (Sticky Session)"""
        c1 = create_cred("user1", order=1)
        c2 = create_cred("user2", order=1)

        pool = create_pool([c1, c2])

        # 指定 user2 为偏好凭证
        candidates = list(pool.get_tiered_candidates(preferred_cred=c2))

        # 验证：user2 必须插队到第一位
        assert candidates[0].inner.username == "user2"

        # 验证：user2 不会重复出现 (去重逻辑)
        usernames = [c.inner.username for c in candidates]
        assert usernames.count("user2") == 1
        assert len(usernames) == 2

    def test_scheduling_sticky_invalid(self):
        """测试粘滞会话失效 (Sticky 账号状态异常)"""
        c1 = create_cred("user1", order=1)
        c2 = create_cred("user2", order=1, status=CredentialStatus.INVALID)  # 失效

        pool = create_pool([c1, c2])

        # 指定已失效的 user2 为偏好
        candidates = list(pool.get_tiered_candidates(preferred_cred=c2))

        # 验证：user2 不应该被返回
        usernames = [c.inner.username for c in candidates]
        assert "user2" not in usernames
        assert len(usernames) == 1
        assert usernames[0] == "user1"

    def test_scheduling_status_filtering(self):
        """测试状态过滤 (只返回 ACTIVE)"""
        c1 = create_cred("active", order=1)
        c2 = create_cred("invalid", order=1, status=CredentialStatus.INVALID)
        c3 = create_cred("disabled", order=1, status=CredentialStatus.DISABLED)

        pool = create_pool([c1, c2, c3])

        candidates = list(pool.get_tiered_candidates())

        assert len(candidates) == 1
        assert candidates[0].inner.username == "active"

    def test_pool_cache_behavior(self):
        """测试缓存行为 (_tiered_groups)"""
        c1 = create_cred("user1", order=1)
        pool = create_pool([c1])

        # 第一次调用，生成缓存
        list(pool.get_tiered_candidates())
        assert pool._tiered_groups is not None
        assert len(pool._tiered_groups[1]) == 1

        # 模拟：动态添加了一个新用户到配置中 (绕过 add 方法直接改 list)
        c2 = create_cred("user2", order=1)
        pool.pool.append(c2)

        # 再次调用，因为有缓存，新用户 user2 应该**不可见**
        candidates = list(pool.get_tiered_candidates())
        assert len(candidates) == 1
        assert candidates[0].inner.username == "user1"

        # 手动清除缓存
        pool.evict_iterator_cache()

        # 再次调用，新用户应该出现了
        candidates_new = list(pool.get_tiered_candidates())
        assert len(candidates_new) == 2

    def test_add_removes_cache(self):
        """测试 add/remove/clear 方法是否自动清除缓存"""
        c1 = create_cred("user1", order=1)
        pool = create_pool([c1])

        # 初始化缓存
        list(pool.get_tiered_candidates())
        assert pool._tiered_groups is not None

        # 添加新用户
        c2 = create_cred("user2", order=1)
        pool.add(c2)

        # 验证缓存已被清除
        assert pool._tiered_groups is None
        assert pool._rr_counters is None

        # 验证新用户生效
        candidates = list(pool.get_tiered_candidates())
        assert len(candidates) == 2
