import asyncio
from abc import abstractmethod
from functools import partial
from typing import Callable, Optional

from rich.prompt import Confirm

from kmdr.core.bases import Downloader
from kmdr.core.console import emit, exception, in_toolcall_mode, info, is_interactive, log
from kmdr.core.constants import BookFormat
from kmdr.core.structure import BookInfo, Credential, VolInfo

from .download_utils import format_filename, readable_safe_filename
from .misc import DownloadTracker, construct_callback


class BaseDownloader(Downloader):
    def __init__(self, dest: str = ".", format: str = "epub", callback: Optional[str] = None, retry: int = 3, num_workers: int = 8, explain: bool = False, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._dest: str = dest
        self._format: BookFormat = BookFormat.from_name(format)
        self._callback: Optional[Callable] = construct_callback(callback)
        self._retry: int = retry
        self._semaphore = asyncio.Semaphore(num_workers)
        self._explain: bool = explain

    async def download(self, cred: Credential, book: BookInfo, volumes: list[VolInfo]):
        if not volumes:
            info("没有可下载的卷。", style="blue")
            return

        if self._explain:
            await self._explain_download(cred, book, volumes)
            return

        total_size = sum(v.size or 0 for v in volumes)
        avai = self._avai_quota(cred)
        if avai < total_size:
            if is_interactive():
                should_continue = Confirm.ask(
                    f"[red]警告：当前下载所需额度约为 {total_size:.2f} MB，当前剩余额度 {avai:.2f} MB，可能无法正常完成下载。是否继续下载？[/red]",
                    default=False,
                )

                if not should_continue:
                    info("用户取消下载。")
                    return
            else:
                log(f"[red]警告：当前下载所需额度约为 {total_size:.2f} MB，当前剩余额度 {avai:.2f} MB，可能无法正常完成下载。[/red]")

        tracker = DownloadTracker(len(volumes))
        try:
            with self._progress:
                tasks = [
                    self._download(cred, book, volume, progress_callback=partial(tracker, volume=volume.name, size_mb=volume.size))
                    for volume in volumes
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

            exceptions = [res for res in results if isinstance(res, Exception)]
            if exceptions:
                info(f"[red]下载过程中出现 {len(exceptions)} 个错误：[/red]")
                for exc in exceptions:
                    info(f"[red]- {exc}[/red]")
                    exception(exc)

        except asyncio.CancelledError:
            await asyncio.sleep(0.01)
            raise
        finally:
            # 工具调用模式下的最终汇总输出
            emit(
                book=book.name,
                total=tracker.total,
                completed=tracker.completed,
                failed=tracker.failed,
                skipped=tracker.skipped,
            )

    def _avai_quota(self, cred: Credential) -> float:
        """计算并返回指定 Credential 的可用额度（单位：MB）"""
        return cred.quota_remaining

    async def _explain_download(self, cred: Credential, book: BookInfo, volumes: list[VolInfo]):

        from os import path

        import aiofiles.os as aio_os

        to_download: list[VolInfo] = []
        skipped: list[VolInfo] = []

        destination = f"{self._dest}/{readable_safe_filename(book.name)}"
        if not await aio_os.path.exists(destination):
            to_download = volumes
        else:
            for volume in volumes:
                filename = path.join(destination, format_filename(book.name, volume.name, self._format.name.lower()))
                if await aio_os.path.exists(filename):
                    skipped.append(volume)
                else:
                    to_download.append(volume)

        if in_toolcall_mode():
            estimate_size = sum(v.size or 0 for v in to_download)
            target_path = path.abspath(destination)

            emit(
                book=book.name,
                estimate_quota_usage_mb=round(estimate_size, 2),
                avai_quota_mb=round(self._avai_quota(cred), 2),
                format=self._format.name,
                target_path=target_path,
                to_download=[{"name": v.name, "size": v.size} for v in to_download],
                skipped=[{"name": v.name, "size": v.size} for v in skipped],
            )
        else:
            from rich.markdown import Markdown
            from rich.panel import Panel
            from rich.table import Table

            estimate_size = sum(v.size or 0 for v in to_download)
            target_path = path.abspath(destination)

            self._console.print(Markdown(f"# 下载计划预估：{book.name}"))
            self._console.print()
            self._console.print(Markdown(f"- **目标路径**: `{target_path}`"))

            summary_grid = Table.grid(padding=(0, 4), expand=True)
            summary_grid.add_column(ratio=1)
            summary_grid.add_column(ratio=1)

            col1_md = (
                f"- **下载格式**: `{self._format.name}`\n"
                f"- **需要下载**: `{len(to_download)}` 卷\n"
                f"- **跳过现存**: `{len(skipped)}` 卷"
            )
            col2_md = (
                f"- **预估消耗**: `{estimate_size:.2f} MB`\n"
                f"- **剩余配额**: `{self._avai_quota(cred):.2f} MB`"
            )

            summary_grid.add_row(Markdown(col1_md), Markdown(col2_md))
            self._console.print(summary_grid)
            self._console.print()

            grid = Table.grid(padding=(0, 2), expand=True)
            renderables = []

            if to_download:
                grid.add_column(ratio=1)
                download_lines = []
                for v in to_download:
                    size_info = f"{v.size:.2f} MB" if v.size is not None else "未知"
                    download_lines.append(f"- **{v.name}** (`{size_info}`)")
                renderables.append(Panel(Markdown("\n".join(download_lines)), title="待下载列表", border_style="cyan"))

            if skipped:
                grid.add_column(ratio=1)
                skipped_lines = []
                for v in skipped:
                    skipped_lines.append(f"- *{v.name}*")
                renderables.append(Panel(Markdown("\n".join(skipped_lines)), title="已存在列表", border_style="dim"))

            if renderables:
                grid.add_row(*renderables)
                self._console.print(grid)
                self._console.print()


    @abstractmethod
    async def _download(
        self,
        cred: Credential,
        book: BookInfo,
        volume: VolInfo,
        quota_deduct_callback: Optional[Callable[[bool], None]] = None,
        progress_callback: Optional[Callable[..., None]] = None,
    ):
        """
        供子类实现的实际下载方法。

        :param cred: 用于下载的凭证
        :param book: 要下载的书籍信息
        :param volume: 要下载的卷信息
        :param quota_deduct_callback: 可选的额度扣除回调函数，接受一个布尔值参数，表示额度是否被扣除
        :param progress_callback: 可选的进度回调函数
        """
        ...
