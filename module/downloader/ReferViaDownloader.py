from core import Downloader, VolInfo, DOWNLOADER, BookInfo

from .utils import download_file, safe_filename

try:
    import cloudscraper
except ImportError:
    cloudscraper = None

@DOWNLOADER.register(order=10)
class ReferViaDownloader(Downloader):
    def __init__(self, dest, callback=None, retry=3, num_workers=1, *args, **kwargs):
        super().__init__(dest, callback, retry, num_workers, *args, **kwargs)

        if cloudscraper:
            self._scraper = cloudscraper.create_scraper()
        else:
            self._scraper = None

    def _download(self, book: BookInfo, volume: VolInfo, retry: int):
        sub_dir = safe_filename(book.name)
        download_path = f'{self._dest}/{sub_dir}'

        download_file(
            self._session if not self._scraper else self._scraper,
            self.fetch_download_url(book, volume),
            download_path,
            f'[Kmoe][{book.name}][{volume.name}].epub',
            retry,
            headers={
                "X-Km-From": "kb_http_down"
            },
            callback=lambda: self._callback(book, volume) if self._callback else None
        )

    def fetch_download_url(self, book: BookInfo, volume: VolInfo) -> str:
        response = self._session.get(f"https://kox.moe/getdownurl.php?b={book.id}&v={volume.id}&mobi=2&vip=0&json=1")
        response.raise_for_status()
        data = response.json()
        if data.get('code') != 200:
            raise Exception(f"Failed to fetch download URL: {data.get('msg', 'Unknown error')}")
        
        return data['url']
