from core import Downloader, VolInfo, download_file

class DirectDownloader(Downloader):
    def __init__(self, dest_dir, book, volumes, callback=None, retry_times=3, *args, **kwargs):
        super().__init__(dest_dir, book, volumes, callback, retry_times, *args, **kwargs)

    def download(self):

        for volume in self._volumes:
            self._download(volume, self._retry_times)

    def _download(self, volume: VolInfo, retry_times: int):
        sub_dir = f'{self._book.name}'
        download_path = f'{self._dest_dir}/{sub_dir}'

        download_file(
            self._session, 
            self.construct_download_url(volume),
            download_path,
            volume.name,
            retry_times,
            headers={},
            callback=lambda : self._callback(volume) if self._callback else None
        )

    def construct_download_url(self, volume: VolInfo) -> str:
        return f'https://kox.moe/dl/{self._book.id}/{volume.id}/1/2/0/'
