from functools import partial

from kmdr.core import Downloader, BookInfo, VolInfo, DOWNLOADER
from kmdr.core.constants import API_ROUTE
from kmdr.core.structure import Credential

from .download_utils import download_file_multipart, readable_safe_filename, download_file

@DOWNLOADER.register(
    hasvalues={
        'method': 2
    }
)
class DirectDownloader(Downloader):
    def __init__(self, dest='.', callback=None, retry=3, num_workers=8, proxy=None, vip=False, disable_multi_part=False, *args, **kwargs):
        super().__init__(dest, callback, retry, num_workers, proxy, *args, **kwargs)
        self._use_vip = vip
        self._disable_multi_part = disable_multi_part

    async def _download(self, cred: Credential, book: BookInfo, volume: VolInfo):
        sub_dir = readable_safe_filename(book.name)
        download_path = f'{self._dest}/{sub_dir}'

        if self._disable_multi_part:
            await download_file(
                self._session,
                self._semaphore,
                self._progress,
                partial(self.construct_download_url, cred, book, volume),
                download_path,
                readable_safe_filename(f'[Kmoe][{book.name}][{volume.name}].epub'),
                self._retry,
                cookies=cred.cookies,
                callback=lambda: self._callback(book, volume) if self._callback else None
            )
            return

        await download_file_multipart(
            self._session,
            self._semaphore,
            self._progress,
            partial(self.construct_download_url, cred, book, volume),
            download_path,
            readable_safe_filename(f'[Kmoe][{book.name}][{volume.name}].epub'),
            self._retry,
            cookies=cred.cookies,
            callback=lambda: self._callback(book, volume) if self._callback else None
        )

    def construct_download_url(self, cred: Credential, book: BookInfo, volume: VolInfo) -> str:
        return API_ROUTE.DOWNLOAD.format(
            book_id=book.id,
            volume_id=volume.id,
            is_vip=cred.is_vip if self._use_vip else 0
        )
