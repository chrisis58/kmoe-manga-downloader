from collections.abc import Awaitable
from typing import Callable

from kmdr.core import BookInfo, Credential
from kmdr.core.bases import CATALOGERS, Cataloger
from kmdr.core.constants import API_ROUTE
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
    async def _list_followed_books(self, cookies: dict[str, str]) -> list[BookInfo]:
        from bs4 import BeautifulSoup

        async with self._session.get(API_ROUTE.MY_FOLLOW, cookies=cookies) as response:
            response.raise_for_status()
            html_text = await response.text()

            followed_rows = BeautifulSoup(html_text, "html.parser").find_all("tr", style="height:36px;")
            mapped = map(lambda x: x.find_all("td"), followed_rows)
            filtered = filter(lambda x: "書名" not in x[1].text, mapped)
            books = list(
                map(
                    lambda x: BookInfo(
                        name=x[1].text.strip(),
                        url=x[1].find("a")["href"],
                        author=x[2].text.strip(),
                        status=x[-1].text.strip(),
                        last_update=x[-2].text.strip(),
                        id="",
                    ),
                    filtered,
                )
            )

        return books
