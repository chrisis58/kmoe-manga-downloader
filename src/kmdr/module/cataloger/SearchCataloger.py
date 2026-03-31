from collections.abc import Awaitable
from typing import Callable
from urllib.parse import quote

from rich.table import Table

from kmdr.core import BookInfo, Credential
from kmdr.core.bases import CATALOGERS, Cataloger
from kmdr.core.console import emit, info, in_toolcall_mode
from kmdr.core.constants import API_ROUTE


@CATALOGERS.register(hasvalues={"command": "search"}, hasattrs=frozenset({"keyword"}))
class SearchCataloger(Cataloger):
    def __init__(self, keyword: str, page: int = 1, minimal: bool = False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._keyword = keyword
        self._page = page
        self._minimal = minimal

    async def catalog(
        self, awaitable_cred: Callable[[], Awaitable[Credential]]
    ) -> list[BookInfo]:
        url = API_ROUTE.SEARCH.format(keyword=quote(self._keyword), page=self._page)

        cred: Credential = await awaitable_cred()

        with self._console.status("正在搜索..."):
            async with self._session.get(url, cookies=cred.cookies) as response:
                response.raise_for_status()
                html = await response.text()

                from .utils import extract_search_results

                books, total_pages = extract_search_results(html)

                if in_toolcall_mode():
                    if self._minimal:
                        # 仅返回名字和链接
                        simple_books = [{"name": b.name, "url": b.url} for b in books]
                        emit(total_pages=total_pages, page=self._page, count=len(books), books=simple_books)
                    else:
                        emit(total_pages=total_pages, page=self._page, count=len(books), books=books)
                else:
                    table = Table(title=f"搜索 '{self._keyword}' 的结果 [第 {self._page}/{total_pages} 页]", show_header=True, header_style="bold blue")
                    table.add_column("书名", style="cyan")
                    table.add_column("作者", style="green")
                    table.add_column("状态", style="blue")

                    for book in books:
                        # 核心目标：让书名直接承载超链接
                        display_name = f"[link={book.url}]{book.name}[/link]"
                        table.add_row(display_name, book.author, book.status)

                    info(table)

                return books
