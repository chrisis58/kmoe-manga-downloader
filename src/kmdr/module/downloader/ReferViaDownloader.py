from functools import partial
from typing import Callable, Optional

import json
import aiohttp

from kmdr.core import Downloader, VolInfo, DOWNLOADER, BookInfo
from kmdr.core.constants import API_ROUTE
from kmdr.core.error import QuotaExceededError
from kmdr.core.structure import Credential
from kmdr.core.utils import async_retry
from kmdr.core.console import debug

from .download_utils import download_file, download_file_multipart, readable_safe_filename

DOWNLOAD_HEAD = {
    "X-Km-From": "kb_http_down",
}

@DOWNLOADER.register(order=10)
class ReferViaDownloader(Downloader):
    def __init__(self, dest='.', callback=None, retry=3, num_workers=8, proxy=None, vip=False, disable_multi_part=False, try_multi_part=False, *args, **kwargs):
        super().__init__(dest, callback, retry, num_workers, proxy, *args, **kwargs)
        self._use_vip = vip
        self._disable_multi_part = disable_multi_part
        self._try_multi_part = try_multi_part

    async def _download(self, cred: Credential, book: BookInfo, volume: VolInfo, quota_deduct_callback: Optional[Callable[[bool], None]] = None):
        sub_dir = readable_safe_filename(book.name)
        download_path = f'{self._dest}/{sub_dir}'

        if self._disable_multi_part or (not cred.is_vip and not self._try_multi_part):
            # 2025/11: 服务器对于普通用户似乎不支持分片下载
            # 所以这里对普通用户默认使用完整下载，如果想要尝试分片下载，可以使用 --try-multi-part 参数
            # 参考 issue: https://github.com/chrisis58/kmoe-manga-downloader/issues/28
            await download_file(
                self._session,
                self._semaphore,
                self._progress,
                partial(self.fetch_download_url, quota_deduct_callback, cred.cookies, cred.is_vip, book.id, volume.id),
                download_path,
                readable_safe_filename(f'[Kmoe][{book.name}][{volume.name}].epub'),
                self._retry,
                headers=DOWNLOAD_HEAD,
                callback=lambda: self._callback(book, volume) if self._callback else None,
                resumable=cred.is_vip, # 仅 VIP 用户支持断点续传
            )
            return

        await download_file_multipart(
            self._session,
            self._semaphore,
            self._progress,
            partial(self.fetch_download_url, quota_deduct_callback, cred.cookies, cred.is_vip, book.id, volume.id),
            download_path,
            readable_safe_filename(f'[Kmoe][{book.name}][{volume.name}].epub'),
            self._retry,
            headers=DOWNLOAD_HEAD,
            callback=lambda: self._callback(book, volume) if self._callback else None
        )

    @async_retry(delay=3, backoff=1.5)
    async def fetch_download_url(self, quota_deduct_callback: Optional[Callable[[bool], None]], cookies: dict, is_vip: bool, book_id: str, volume_id: str) -> str:

        async with self._session.get(
            API_ROUTE.GETDOWNURL.format(
                book_id=book_id,
                volume_id=volume_id,
                is_vip=is_vip if self._use_vip else 0
            ),
            cookies=cookies,
        ) as response:
            response.raise_for_status()
            quota_deduct_callback(True) if quota_deduct_callback else None
            data = await response.text()
            data = json.loads(data)
            debug("获取下载链接响应数据:", data)
            if (code := data.get('code')) != 200:

                msg = data.get('msg', '__未知错误__')
                debug(f"获取下载链接失败，错误码 {code}，信息: {msg}")

                if "達到下載額度限制" in msg:
                    raise QuotaExceededError(msg)

                raise aiohttp.ClientResponseError(
                    response.request_info,
                    history=response.history,
                    status=code,
                    message=msg
                )

            return data['url']
