from functools import partial

import json
import aiohttp
from async_lru import alru_cache

from kmdr.core import Downloader, VolInfo, DOWNLOADER, BookInfo
from kmdr.core.constants import API_ROUTE
from kmdr.core.error import ResponseError
from kmdr.core.utils import async_retry
from kmdr.core.console import debug

from .download_utils import download_file_multipart, readable_safe_filename


@DOWNLOADER.register(order=10)
class ReferViaDownloader(Downloader):
    def __init__(self, dest='.', callback=None, retry=3, num_workers=8, proxy=None, vip=False, *args, **kwargs):
        super().__init__(dest, callback, retry, num_workers, proxy, *args, **kwargs)
        self._use_vip = vip

    async def _download(self, book: BookInfo, volume: VolInfo):
        sub_dir = readable_safe_filename(book.name)
        download_path = f'{self._dest}/{sub_dir}'

        await download_file_multipart(
            self._session,
            self._semaphore,
            self._progress,
            partial(self.fetch_download_url, book.id, volume.id),
            download_path,
            readable_safe_filename(f'[Kmoe][{book.name}][{volume.name}].epub'),
            self._retry,
            headers={
                "X-Km-From": "kb_http_down"
            },
            callback=lambda: self._callback(book, volume) if self._callback else None
        )

    @alru_cache(maxsize=128)
    @async_retry()
    async def fetch_download_url(self, book_id: str, volume_id: str) -> str:

        async with self._session.get(
            API_ROUTE.GETDOWNURL.format(
                book_id=book_id,
                volume_id=volume_id,
                is_vip=self._profile.is_vip if self._use_vip else 0
            )
        ) as response:
            response.raise_for_status()
            data = await response.text()
            data = json.loads(data)
            debug("获取下载链接响应数据:", data)
            if (code := data.get('code')) != 200:

                if code in {401, 403, 404}:
                    raise ResponseError("无法获取下载链接" + data.get('msg', 'Unknown error'), code)

                raise aiohttp.ClientResponseError(
                    response.request_info,
                    history=response.history,
                    status=code,
                    message=data.get('msg', 'Unknown error')
                )

            return data['url']
