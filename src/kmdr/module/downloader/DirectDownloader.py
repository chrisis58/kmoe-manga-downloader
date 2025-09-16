from kmdr.core import Downloader, BookInfo, VolInfo, DOWNLOADER

from .utils import download_file, safe_filename

@DOWNLOADER.register(
    hasvalues={
        'method': 1
    }
)
class DirectDownloader(Downloader):
    def __init__(self, dest='.', callback=None, retry=3, num_workers=8, proxy=None, *args, **kwargs):
        super().__init__(dest, callback, retry, num_workers, proxy, *args, **kwargs)

    async def _download(self, book: BookInfo, volume: VolInfo, retry: int):
        sub_dir = safe_filename(book.name)
        download_path = f'{self._dest}/{sub_dir}'

        await download_file(
            self._session,
            lambda: self.construct_download_url(book, volume),
            download_path,
            safe_filename(f'[Kmoe][{book.name}][{volume.name}].epub'),
            retry,
            callback=lambda: self._callback(book, volume) if self._callback else None
        )

    def construct_download_url(self, book: BookInfo, volume: VolInfo) -> str:
        return f'https://kox.moe/dl/{book.id}/{volume.id}/1/2/{self._profile.is_vip}/'
