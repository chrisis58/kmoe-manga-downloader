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

class TestPooledCredential(unittest.TestCase):

    def setUp(self):
        # User配额 100/10，VIP配额 500/0
        self.base_cred = create_cred("pool_user", is_vip=True)
        self.pooled = PooledCredential(self.base_cred)

    def test_reserve_success(self):
        """预留流量成功时应更新 reserved 字段"""
        # 剩余 90 (100-10)
        # 尝试预留 50 -> 成功
        handle = self.pooled.reserve(50.0)
        self.assertIsNotNone(handle)
        self.assertEqual(self.pooled.reserved, 50.0)

    def test_reserve_fail_insufficient(self):
        """预留流量失败时 reserved 字段不应改变"""
        # 剩余 600
        # 尝试预留 600 -> 失败
        handle = self.pooled.reserve(600.0)
        self.assertIsNone(handle)
        self.assertEqual(self.pooled.reserved, 0.0)

    def test_commit(self):
        """提交预留流量后应更新 unsynced_usage 和 reserved"""
        # 预留 20
        handle = self.pooled.reserve(20.0)
        # 提交 20
        self.pooled.commit(handle, is_vip=False)

        print(self.pooled.inner.user_quota)

        self.assertEqual(self.pooled.reserved, 0.0)
        self.assertEqual(self.base_cred.user_quota.remaining, 70.0)
        self.assertEqual(self.base_cred.user_quota.unsynced_usage, 20.0)
        
    def test_rollback(self):
        """回滚预留流量后应更新 reserved 字段"""
        # 预留 20
        handle = self.pooled.reserve(20.0)
        # 回滚 20
        self.pooled.rollback(handle)

        self.assertEqual(self.pooled.reserved, 0.0)
        self.assertEqual(self.base_cred.user_quota.unsynced_usage, 0.0)

    def test_update_from_server(self):
        """从服务端更新凭证信息应覆盖本地数据"""
        # 本地有 unsynced 数据
        self.base_cred.user_quota.unsynced_usage = 50.0
        
        # 服务端发来新数据
        server_cred = create_cred("pool_user", is_vip=True)
        server_cred.user_quota.total = 200.0
        server_cred.user_quota.used = 59.0
        
        self.pooled.update_cred(server_cred, force=True)
        
        self.assertEqual(self.pooled.inner.user_quota.total, 200.0)
        self.assertEqual(self.pooled.inner.user_quota.unsynced_usage, 0.0)
        self.assertEqual(self.pooled.inner.user_quota.used, 59.0)
