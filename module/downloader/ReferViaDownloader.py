from core import Downloader, VolInfo, download_file

class ReferViaDownloader(Downloader):
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
            self.fetch_download_url(volume),
            download_path,
            volume.name,
            retry_times,
            headers={
                "X-Km-From": "kb_http_down"
            },
            callback=lambda: self._callback(volume) if self._callback else None
        )

    def fetch_download_url(self, volume: VolInfo) -> str:
        response = self._session.get(f"https://kox.moe/getdownurl.php?b={self._book.id}&v={volume.id}&mobi=2&vip=0&json=1")
        response.raise_for_status()
        data = response.json()
        if data.get('code') != 200:
            raise Exception(f"Failed to fetch download URL: {data.get('msg', 'Unknown error')}")
        
        return data['url']
