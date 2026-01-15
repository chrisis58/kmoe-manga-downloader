import unittest
import time
from unittest.mock import MagicMock

from kmdr.core.pool import CredentialPool, PooledCredential
from kmdr.core.structure import Credential, CredentialStatus, QuotaInfo, Config

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
        nickname=f"Nick-{username}"
    )

class TestCredentialPool(unittest.TestCase):

    def setUp(self):
        self.mock_configurer = MagicMock()
        self.mock_config = Config()
        self.mock_config.cred_pool = []
        self.mock_configurer.config = self.mock_config
        
        self.pool_mgr = CredentialPool(self.mock_configurer)

    def test_add_and_check_duplicate(self):
        """添加凭证后应能在列表中找到，并且排重逻辑生效"""
        cred = create_cred("user_new")
        self.pool_mgr.add(cred)

        # 验证加入列表
        assert self.mock_config.cred_pool is not None
        self.assertIn(cred, self.mock_config.cred_pool)
        # 验证调用了 save
        self.mock_configurer.update.assert_called()
        # 验证排重逻辑
        self.assertTrue(self.pool_mgr.check_duplicate("user_new"))
        self.assertFalse(self.pool_mgr.check_duplicate("user_not_exist"))

    def test_remove(self):
        """删除凭证后不应在列表中"""
        cred = create_cred("user_rem")
        self.pool_mgr.add(cred)
        
        result = self.pool_mgr.remove("user_rem")
        
        self.assertTrue(result)
        assert self.mock_config.cred_pool is not None
        self.assertEqual(len(self.mock_config.cred_pool), 0)
        self.mock_configurer.update.assert_called()

    def test_update_status(self):
        """更新凭证状态后应反映在对象中"""
        cred = create_cred("user_stat", status=CredentialStatus.ACTIVE)
        self.pool_mgr.add(cred)

        self.pool_mgr.update_status("user_stat", CredentialStatus.DISABLED)
        
        self.assertEqual(cred.status, CredentialStatus.DISABLED)
        self.mock_configurer.update.assert_called()

    def test_active_creds_property_sorts_by_order(self):
        """active_creds 属性应返回活跃用户并按优先级排序"""
        c1 = create_cred("u1", order=10, status=CredentialStatus.ACTIVE)
        c2 = create_cred("u2", order=1, status=CredentialStatus.ACTIVE)
        c3 = create_cred("u3", order=5, status=CredentialStatus.DISABLED) # 不应出现

        self.mock_config.cred_pool = [c1, c2, c3]
        
        active_list = self.pool_mgr.active_creds
        
        self.assertEqual(len(active_list), 2)
        # 顺序应该是 u2(1) -> u1(10)
        self.assertEqual(active_list[0].username, "u2")
        self.assertEqual(active_list[1].username, "u1")

    def test_get_next_cycle_logic(self):
        """get_next 方法应按顺序轮询返回凭证"""
        c1 = create_cred("A", order=1)
        c2 = create_cred("B", order=2)
        self.mock_config.cred_pool = [c1, c2]

        # 第一次获取，应该是 A (order 1)
        n1 = self.pool_mgr.get_next()
        assert n1 is not None
        self.assertEqual(n1.username, "A")

        # 第二次获取，应该是 B (order 2)
        n2 = self.pool_mgr.get_next()
        assert n2 is not None
        self.assertEqual(n2.username, "B")

        # 第三次获取，应该回到 A (Cycle)
        n3 = self.pool_mgr.get_next()
        assert n3 is not None
        self.assertEqual(n3.username, "A")

    def test_get_next_skips_invalid(self):
        """get_next 应自动跳过状态变成非 ACTIVE 的凭证"""
        c1 = create_cred("A", status=CredentialStatus.ACTIVE)
        c2 = create_cred("B", status=CredentialStatus.ACTIVE)
        self.mock_config.cred_pool = [c1, c2]

        # 初始化迭代器
        cred = self.pool_mgr.get_next()
        assert cred is not None
        self.assertEqual(cred.username, "A")

        # 把 B 禁用
        c2.status = CredentialStatus.DISABLED

        # 下一次获取应该跳过 B，直接再次返回 A
        n = self.pool_mgr.get_next()
        assert n is not None
        self.assertEqual(n.username, "A")

    def test_get_next_returns_none_if_empty(self):
        self.mock_config.cred_pool = []
        self.assertIsNone(self.pool_mgr.get_next())

class TestPooledCredential(unittest.TestCase):

    def setUp(self):
        # User配额 100/10，VIP配额 500/0
        self.base_cred = create_cred("pool_user", is_vip=True)
        self.pooled = PooledCredential(self.base_cred)

    def test_init_clears_reserved(self):
        """初始化时应重置 reserved 字段"""
        self.base_cred.user_quota.reserved = 50.0
        p = PooledCredential(self.base_cred)
        self.assertEqual(p.inner.user_quota.reserved, 0.0)

    def test_reserve_success(self):
        """预留流量成功时应更新 reserved 字段"""
        # 剩余 90 (100-10)
        # 尝试预留 50 -> 成功
        success = self.pooled.reserve(50.0, is_vip=False)
        self.assertTrue(success)
        self.assertEqual(self.base_cred.user_quota.reserved, 50.0)

    def test_reserve_fail_insufficient(self):
        """预留流量失败时 reserved 字段不应改变"""
        # 剩余 90
        # 尝试预留 91 -> 失败
        success = self.pooled.reserve(91.0, is_vip=False)
        self.assertFalse(success)
        self.assertEqual(self.base_cred.user_quota.reserved, 0.0)

    def test_commit(self):
        """提交预留流量后应更新 unsynced_usage 和 reserved"""
        # 预留 20
        self.pooled.reserve(20.0, is_vip=False)
        # 提交 20
        self.pooled.commit(20.0, is_vip=False)

        self.assertEqual(self.base_cred.user_quota.reserved, 0.0)
        self.assertEqual(self.base_cred.user_quota.unsynced_usage, 20.0)
        
    def test_rollback(self):
        """回滚预留流量后应更新 reserved 字段"""
        # 预留 20
        self.pooled.reserve(20.0, is_vip=False)
        # 回滚 20
        self.pooled.rollback(20.0, is_vip=False)

        self.assertEqual(self.base_cred.user_quota.reserved, 0.0)
        self.assertEqual(self.base_cred.user_quota.unsynced_usage, 0.0)

    def test_update_from_server(self):
        """从服务端更新凭证信息应覆盖本地数据"""
        # 本地有 unsynced 数据
        self.base_cred.user_quota.unsynced_usage = 50.0
        
        # 服务端发来新数据
        server_cred = create_cred("pool_user", is_vip=True)
        server_cred.user_quota.total = 200.0
        server_cred.user_quota.used = 59.0
        
        self.pooled.update_from_server(server_cred)
        
        self.assertEqual(self.base_cred.user_quota.total, 200.0)
        self.assertEqual(self.base_cred.user_quota.unsynced_usage, 0.0)
        self.assertEqual(self.base_cred.user_quota.used, 59.0)
