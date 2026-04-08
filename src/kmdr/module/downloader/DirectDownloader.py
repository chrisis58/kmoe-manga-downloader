from functools import partial
from typing import Callable, Optional

from kmdr.core import DOWNLOADER, BookInfo, VolInfo
from kmdr.core.constants import API_ROUTE
from kmdr.core.structure import Credential

from .base import BaseDownloader
from .download_utils import (
    download_file,
    download_file_multipart,
    format_filename,
    readable_safe_filename,
)


@DOWNLOADER.register(hasvalues={"method": 2})
class DirectDownloader(BaseDownloader):
    def __init__(
        self, dest=".", format="epub", callback=None, retry=3, num_workers=8, vip=False, disable_multi_part=False, *args, **kwargs
    ):
        super().__init__(dest, format, callback, retry, num_workers, *args, **kwargs)
        self._use_vip = vip
        self._disable_multi_part = disable_multi_part

    async def _download(
        self,
        cred: Credential,
        book: BookInfo,
        volume: VolInfo,
        quota_deduct_callback: Optional[Callable[[bool], None]] = None,
        progress_callback: Optional[Callable[..., None]] = None,
    ):
        sub_dir = readable_safe_filename(book.name)
        download_path = f"{self._dest}/{sub_dir}"

        if self._disable_multi_part:
            await download_file(
                self._session,
                self._semaphore,
                self._progress,
                partial(self.construct_download_url, cred, book, volume),
                download_path,
                format_filename(book.name, volume.name, self._format.name.lower()),
                self._retry,
                cookies=cred.cookies,
                callback=lambda: self._callback(book, volume) if self._callback else None,
                quota_deduct_callback=quota_deduct_callback,
                progress_callback=progress_callback,
            )
            return

        await download_file_multipart(
            self._session,
            self._semaphore,
            self._progress,
            partial(self.construct_download_url, cred, book, volume),
            download_path,
            format_filename(book.name, volume.name, self._format.name.lower()),
            self._retry,
            cookies=cred.cookies,
            callback=lambda: self._callback(book, volume) if self._callback else None,
            quota_deduct_callback=quota_deduct_callback,
            progress_callback=progress_callback,
        )

    def construct_download_url(self, cred: Credential, book: BookInfo, volume: VolInfo) -> str:
        return API_ROUTE.DOWNLOAD.format(
            book_id=book.id,
            volume_id=volume.id,
            book_format=self._format.value,
            is_vip=1 if self._use_vip and cred.is_vip else 0,
        )
