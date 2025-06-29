from core import Downloader, VolInfo, download_file, DOWNLOADER, BookInfo

@DOWNLOADER.register(order=10)
class ReferViaDownloader(Downloader):
    def __init__(self, dest, callback=None, retry=3, *args, **kwargs):
        super().__init__(dest, callback, retry, *args, **kwargs)

    def download(self, book: BookInfo, volumes: list[VolInfo], *args, **kwargs):

        for volume in volumes:
            self._download(book, volume, self._retry)

    def _download(self, book: BookInfo, volume: VolInfo, retry: int):
        sub_dir = f'{book.name}'
        download_path = f'{self._dest}/{sub_dir}'

        download_file(
            self._session,
            self.fetch_download_url(volume),
            download_path,
            volume.name,
            retry,
            headers={
                "X-Km-From": "kb_http_down"
            },
            callback=lambda : self._callback(volume) if self._callback else None
        )

    def fetch_download_url(self, volume: VolInfo) -> str:
        response = self._session.get(f"https://kox.moe/getdownurl.php?b={self._book.id}&v={volume.id}&mobi=2&vip=0&json=1")
        response.raise_for_status()
        data = response.json()
        if data.get('code') != 200:
            raise Exception(f"Failed to fetch download URL: {data.get('msg', 'Unknown error')}")
        
        return data['url']
