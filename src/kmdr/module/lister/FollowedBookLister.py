import asyncio
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from rich.table import Table
from rich.prompt import IntPrompt

from kmdr.core import Lister, LISTERS, BookInfo, VolInfo
from kmdr.core.utils import async_retry
from kmdr.core.constants import API_ROUTE

from .utils import extract_book_info_and_volumes

@LISTERS.register()
class FollowedBookLister(Lister):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def list(self) -> tuple[BookInfo, list[VolInfo]]:
        books = []
        
        with self._console.status("正在获取关注列表..."):
            books = await self._list_followed_books()
        
        if not books:
            self._console.print("[yellow]关注列表为空。[/yellow]")
            exit(0)

        table = Table(title="关注的书籍列表", show_header=True, header_style="bold blue")
        table.add_column("序号", style="dim", width=4, justify="center")
        table.add_column("书名", style="cyan", no_wrap=True)
        table.add_column("作者", style="green")
        table.add_column("最后更新", style="yellow")
        table.add_column("状态", style="blue")

        for idx, book in enumerate(books):
            table.add_row(
                str(idx + 1),
                book.name,
                book.author,
                book.last_update,
                book.status
            )
        
        self._console.print(table)

        valid_choices = [str(i) for i in range(1, len(books) + 1)]
        
        chosen_idx = await asyncio.to_thread(
            IntPrompt.ask,
            "请选择要下载的书籍序号",
            choices=valid_choices,
            show_choices=False,
            show_default=False
        )
        
        book_to_download = books[chosen_idx - 1]

        with self._console.status(f"正在获取 '{book_to_download.name}' 的详细信息..."):
            book_info, volumes = await extract_book_info_and_volumes(self._session, book_to_download.url, book_to_download)
            return book_info, volumes
    
    @async_retry()
    async def _list_followed_books(self) -> 'list[BookInfo]':
        async with self._session.get(urljoin(self._base_url, API_ROUTE.MY_FOLLOW)) as response:
            response.raise_for_status()
            html_text = await response.text()

            # 如果后续有性能问题，可以先考虑使用 lxml 进行解析
            followed_rows = BeautifulSoup(html_text, 'html.parser').find_all('tr', style='height:36px;')
            mapped = map(lambda x: x.find_all('td'), followed_rows)
            filtered = filter(lambda x: '書名' not in x[1].text, mapped)
            books = list(map(lambda x: BookInfo(name=x[1].text.strip(), url=x[1].find('a')['href'], author=x[2].text.strip(), status=x[-1].text.strip(), last_update=x[-2].text.strip(), id=''), filtered))
        
        return books