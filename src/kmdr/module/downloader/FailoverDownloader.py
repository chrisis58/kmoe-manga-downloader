from kmdr.core.context import CredentialPoolContext
from kmdr.core.bases import DOWNLOADER, Downloader
from kmdr.core.error import LoginError
from kmdr.core.structure import BookInfo, Credential, VolInfo, CredentialStatus
from kmdr.core.pool import CredentialPool, PooledCredential
from kmdr.core.console import debug, info
from kmdr.core.error import QuotaExceededError

from kmdr.module.authenticator.utils import check_status


@DOWNLOADER.register(
    hasvalues={'use_pool': True},
    order=-99, # 确保优先匹配
)
class FailoverDownloader(Downloader, CredentialPoolContext):
    """实现了故障转移的下载器，根据用户选择的下载方法，委托给具体的下载器实现。"""

    def __init__(self, method: int, num_workers: int = 8, per_cred_ratio: float = 1.0, *args, **kwargs):
        super().__init__(num_workers=num_workers, per_cred_ratio=per_cred_ratio, *args, **kwargs)

        self._num_workers_per_cred = max(1, int(num_workers * per_cred_ratio))

        if method not in (1, 2):
            debug("未知的下载方法，默认使用 ReferViaDownloader。")

        if method == 2:
            from .DirectDownloader import DirectDownloader
            self._delegate = DirectDownloader(num_workers=num_workers, per_cred_ratio=per_cred_ratio, *args, **kwargs)
        else:
            # 默认使用 ReferViaDownloader
            from .ReferViaDownloader import ReferViaDownloader
            self._delegate = ReferViaDownloader(num_workers=num_workers, per_cred_ratio=per_cred_ratio, *args, **kwargs)


    async def _download(self, cred: Credential, book: BookInfo, volume: VolInfo):
        """使用凭证池中的账号下载指定的卷，遇到额度不足或登录失效时自动切换账号继续下载。"""
        required_size = volume.size or 0.0

        # 给予足够的重试次数 (池子大小 * 2)，确保能轮询所有账号
        max_attempts = max(1, self._pool.active_count * 2)
        attempts = 0

        pooled_cred = self._pool.get_pooled(cred, self._num_workers_per_cred)

        while attempts < max_attempts:
            async with pooled_cred.download_semaphore:
                attempts += 1

                if attempts > 1:
                    # 重试时才切换凭证
                    pooled_cred = self._pool.get_next(max_workers=self._num_workers_per_cred)
                    if not pooled_cred:
                        raise RuntimeError("凭证池已耗尽，无法继续下载。")
                    debug("尝试使用账号", pooled_cred.inner.username, "进行卷", volume.name, "的下载...")

                if pooled_cred.inner.quota_remaining < required_size:
                    # 如果当前凭证余额不足以支付下载，跳过
                    debug(f"账号", pooled_cred.inner.username, "余额不足，跳过。需要", required_size, "MB，剩余", pooled_cred.inner.quota_remaining, "MB")
                    continue

                if pooled_cred.inner.status == CredentialStatus.INVALID:
                    continue

                try:
                    pooled_cred.reserve(required_size)
                    # 委托具体的下载器实现下载
                    await self._delegate._download(pooled_cred.inner, book, volume)
                    
                    pooled_cred.commit(required_size)
                    return

                except QuotaExceededError:
                    pooled_cred.rollback(required_size)
                    info(f"[yellow]账号 {pooled_cred.inner.username} 提示额度不足，正在同步状态...[/yellow]")

                    # 在判断是否额度全部用尽前，先尝试同步状态                    
                    await self.__refresh_cred(pooled_cred)

                    if pooled_cred.inner.status != CredentialStatus.ACTIVE:
                        info(f"账号 {pooled_cred.inner.username} 状态已变更为 {pooled_cred.inner.status}，跳过。")
                        continue

                    if pooled_cred.inner.quota_remaining < 0.1:
                        self._pool.update_status(pooled_cred.inner.username, CredentialStatus.QUOTA_EXCEEDED)
                    else:
                        info(f"账号 {pooled_cred.inner.username} 更新后余额 {pooled_cred.inner.quota_remaining:.2f}MB，仍不足以支付 ({required_size:.2f}MB)")

                    continue

                except LoginError:
                    pooled_cred.rollback(required_size)
                    info(f"账号 {pooled_cred.inner.username} 登录失效。")
                    self._pool.update_status(pooled_cred.inner.username, CredentialStatus.INVALID)
                    continue

                except Exception:
                    pooled_cred.rollback(required_size)
                    info(f"下载卷 {volume.name} 时，账号 {pooled_cred.inner.username} 遇到无法处理的异常。")
                    raise

            raise RuntimeError(f"尝试了 {attempts} 次，无可用的凭证下载卷: {volume.name}")


    async def __refresh_cred(self, pooled_cred: PooledCredential) -> None:
        if pooled_cred.is_recently_synced():
            debug(f"账号 {pooled_cred.inner.username} 最近已同步，使用缓存数据。")
            return

        try:
            async with pooled_cred.update_lock:
                # 双重检查
                if pooled_cred.is_recently_synced():
                    debug(f"账号 {pooled_cred.inner.username} 已被同步，跳过请求。")
                    return

                debug(f"正在从服务器同步账号 {pooled_cred.inner.username} 的状态...")

                new_info = await check_status(
                    session=self._session, 
                    console=self._console,
                    username=pooled_cred.inner.username, 
                    cookies=pooled_cred.inner.cookies
                )

                pooled_cred.update_cred(new_info, force=True)
                debug("账号", pooled_cred.inner.username, "同步完成。剩余额度:", pooled_cred.inner.quota_remaining, "MB")
                return
        except Exception as e:
            info(f"同步账号 {pooled_cred.inner.username} 失败")
            debug(f"错误信息: {e}")
            self._pool.update_status(pooled_cred.inner.username, CredentialStatus.INVALID)
