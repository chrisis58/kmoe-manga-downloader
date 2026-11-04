from collections.abc import Awaitable
from typing import Callable

from kmdr.core import BookInfo, Credential
from kmdr.core.bases import CATALOGERS, Cataloger
from kmdr.core.console import info
from kmdr.core.constants import API_ROUTE
from kmdr.core.error import HtmlResolveError
from kmdr.core.utils import async_retry


@CATALOGERS.register(order=99)
class FollowedCataloger(Cataloger):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def catalog(self, awaitable_cred: Callable[[], Awaitable[Credential]]) -> list[BookInfo]:
        cred: Credential = await awaitable_cred()
        with self._console.status("正在获取关注列表..."):
            return await self._list_followed_books(cookies=cred.cookies)

    @async_retry()
    async def _list_followed_books(self, cookies: dict[str, str]) -> "list[BookInfo]":
        from bs4 import BeautifulSoup, Tag

        async with self._session.get(API_ROUTE.MY_FOLLOW, cookies=cookies) as response:
            response.raise_for_status()
            html_text = await response.text()

            # 如果后续有性能问题，可以先考虑使用 lxml 进行解析
            followed_rows = BeautifulSoup(html_text, "html.parser").find_all("tr", style="height:36px;")
            if not followed_rows:
                raise HtmlResolveError("关注列表页未找到高度为 36px 的记录行，无法确认列表是否为空", code="FOLLOW_ROWS_MISSING")

            books = []
            skipped = 0
            for row in followed_rows:
                if not isinstance(row, Tag):
                    continue

                cells = row.find_all("td")
                if len(cells) < 2:
                    skipped += 1
                    continue

                name_cell = cells[1]
                if not isinstance(name_cell, Tag):
                    raise HtmlResolveError("关注列表记录的第二列不是有效的书名单元格", code="FOLLOW_NAME_CELL_INVALID")

                # 表头行：书名列显示“書名”而非具体书名
                if name_cell.text.strip() == "書名":
                    continue

                link = name_cell.find("a")
                if not isinstance(link, Tag):
                    skipped += 1
                    continue

                href = link.get("href")
                if not isinstance(href, str) or not href:
                    skipped += 1
                    continue

                if len(cells) < 5:
                    info("[yellow]部分关注书籍缺少作者、状态或更新时间，仍可选择下载。[/yellow]")

                books.append(
                    BookInfo(
                        name=name_cell.text.strip(),
                        url=href,
                        author=cells[2].text.strip() if len(cells) >= 3 else "",
                        status=cells[-1].text.strip() if len(cells) >= 5 else "",
                        last_update=cells[-2].text.strip() if len(cells) >= 5 else "",
                        id="",
                    )
                )

            if skipped:
                if not books:
                    raise HtmlResolveError("关注列表记录均无法提取有效的书籍链接", code="FOLLOW_BOOKS_UNRESOLVABLE")
                info(f"[yellow]已跳过 {skipped} 条无法解析的关注记录，其余书籍仍可下载。[/yellow]")

        return books
