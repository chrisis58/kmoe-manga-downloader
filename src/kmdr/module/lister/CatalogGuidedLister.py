import asyncio
from argparse import Namespace
from collections.abc import Awaitable
from typing import Callable

from rich.prompt import IntPrompt
from rich.table import Table

from kmdr.core import LISTERS, BookInfo, Credential, Lister, VolInfo
from kmdr.core.bases import CATALOGERS
from kmdr.core.console import info, is_interactive
from kmdr.core.error import EmptyResultError, NotInteractableError


@LISTERS.register(order=99)
class CatalogGuidedLister(Lister):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 保存传入的参数字典，用于重构成 Namespace 供 CATALOGERS 调度
        self._kwargs = kwargs

    async def list(self, awaitable_cred: Callable[[], Awaitable[Credential]]) -> tuple[BookInfo, list[VolInfo]]:
        from .utils import extract_book_info_and_volumes

        if not is_interactive():
            raise NotInteractableError("无法交互式选择书籍。")

        mock_args = Namespace(**self._kwargs)
        cataloger = CATALOGERS.get(mock_args)

        books = await cataloger.catalog(awaitable_cred=awaitable_cred)

        if not books:
            raise EmptyResultError("结果列表为空。")

        table = Table(title="书籍列表", show_header=True, header_style="bold blue")
        table.add_column("序号", style="dim", width=4, justify="center")
        table.add_column("书名", style="cyan", no_wrap=True)
        table.add_column("作者", style="green")
        table.add_column("最后更新", style="yellow")
        table.add_column("状态", style="blue")

        for idx, book in enumerate(books):
            table.add_row(str(idx + 1), book.name, book.author, book.last_update, book.status)

        info(table)

        valid_choices = [str(i) for i in range(1, len(books) + 1)]

        chosen_idx = await asyncio.to_thread(
            IntPrompt.ask,
            "请选择要下载的书籍序号",
            choices=valid_choices,
            show_choices=False,
            show_default=False,
        )

        selected_book = books[chosen_idx - 1]

        with self._console.status(f"正在获取 '{selected_book.name}' 的详细信息..."):
            book_info, volumes = await extract_book_info_and_volumes(self._session, selected_book.url, selected_book, awaitable_cred=awaitable_cred)
            return book_info, volumes
