from kmdr.core import Lister, LISTERS, BookInfo, VolInfo

from .utils import extract_book_info_and_volumes


@LISTERS.register()
class BookUrlLister(Lister):

    def __init__(self, book_url: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._book_url = book_url

    async def list(self) -> tuple[BookInfo, list[VolInfo]]:
        with self._console.status("获取书籍信息..."):
            book_info, volumes = await extract_book_info_and_volumes(self._session, self._book_url)
            return book_info, volumes
