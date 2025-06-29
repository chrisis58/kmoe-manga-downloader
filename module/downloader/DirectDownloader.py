from core import Downloader, BookInfo, VolInfo, download_file, DOWNLOADER
from core import haskeys, hasvalues

@DOWNLOADER.register(
    hasvalues={
        'method': 1
    }
)
class DirectDownloader(Downloader):
    def __init__(self, dest, callback=None, retry=3, *args, **kwargs):
        super().__init__(dest, callback, retry, *args, **kwargs)

    def download(self, book: BookInfo, volumes: list[VolInfo]):

        for volume in volumes:
            self._download(book, volume, self._retry)

    def _download(self, book: BookInfo, volume: VolInfo, retry: int):
        sub_dir = f'{book.name}'
        download_path = f'{self._dest}/{sub_dir}'

        download_file(
            self._session,
            self.construct_download_url(volume),
            download_path,
            f'[kmoe][{book.name}][{volume.name}].epub',
            retry,
            headers={},
            callback=lambda : self._callback(volume) if self._callback else None
        )

    def construct_download_url(self, volume: VolInfo) -> str:
        return f'https://kox.moe/dl/{self._book.id}/{volume.id}/1/2/0/'
