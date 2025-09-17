import asyncio
import os
import re
from typing import Callable, Optional, Union, Awaitable

from deprecation import deprecated
import aiohttp
import aiofiles
import aiofiles.os as aio_os
from rich.progress import Progress
from aiohttp.client_exceptions import ClientPayloadError

BLOCK_SIZE_REDUCTION_FACTOR = 0.75
MIN_BLOCK_SIZE = 2048

@deprecated(details="最新版本中改用分片下载，建议使用 'download_file_multipart'")
async def download_file(
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        progress: Progress,
        url: Union[str, Callable[[], str], Callable[[], Awaitable[str]]],
        dest_path: str,
        filename: str,
        retry_times: int = 3,
        headers: Optional[dict] = None,
        callback: Optional[Callable] = None,
):
    """
    下载文件

    :param session: requests.Session 对象
    :param url: 下载链接或者其 Supplier
    :param dest_path: 目标路径
    :param filename: 文件名
    :param retry_times: 重试次数
    :param headers: 请求头
    :param callback: 下载完成后的回调函数
    """
    if headers is None:
        headers = {}

    file_path = os.path.join(dest_path, filename)
    filename_downloading = f'{file_path}.downloading'

    if not await aio_os.path.exists(dest_path):
        await aio_os.makedirs(dest_path, exist_ok=True)

    if await aio_os.path.exists(file_path):
        progress.console.print(f"[yellow]{filename} already exists[/yellow]")
        return

    block_size = 8192
    attempts_left = retry_times + 1
    task_id = None

    try:
        while attempts_left > 0:
            attempts_left -= 1
            
            resume_from = (await aio_os.stat(filename_downloading)).st_size if await aio_os.path.exists(filename_downloading) else 0
            
            if resume_from:
                headers['Range'] = f'bytes={resume_from}-'

            try:
                async with semaphore:
                    current_url = await fetch_url(url)
                    async with session.get(url=current_url, headers=headers) as r:
                        r.raise_for_status()

                        total_size_in_bytes = int(r.headers.get('content-length', 0)) + resume_from

                        if task_id is None:
                            task_id = progress.add_task("download", filename=filename, total=total_size_in_bytes, completed=resume_from, status="[cyan]下载中[/cyan]")
                        else:
                            progress.update(task_id, total=total_size_in_bytes, completed=resume_from, status="[cyan]下载中[/cyan]")
                        
                        async with aiofiles.open(filename_downloading, 'ab') as f:
                            async for chunk in r.content.iter_chunked(block_size):
                                if chunk:
                                    await f.write(chunk)
                                    progress.update(task_id, advance=len(chunk))
                        
                        break 
            
            except Exception as e:
                if attempts_left > 0:
                    if task_id is not None:
                        progress.update(task_id, status=f"[yellow]重试中[/yellow]")
                    if isinstance(e, ClientPayloadError):
                        new_block_size = max(int(block_size * BLOCK_SIZE_REDUCTION_FACTOR), MIN_BLOCK_SIZE)
                        if new_block_size < block_size:
                            block_size = new_block_size
                    await asyncio.sleep(3)
                else:
                    raise e
        
        else: 
            raise IOError(f"Failed to download {filename} after {retry_times} retries.")

        os.rename(filename_downloading, file_path)
    
    except Exception as e:
        if task_id is not None:
            progress.update(task_id, status='[red]失败[/red]', visible=False)

    finally:
        if await aio_os.path.exists(file_path):
            if task_id is not None:
                progress.update(task_id, status='[green]完成[/green]', visible=False)

            if callback:
                callback()

def safe_filename(name: str) -> str:
    """
    替换非法文件名字符为下划线
    """
    return re.sub(r'[\\/:*?"<>|]', '_', name)

async def fetch_url(url: Union[str, Callable[[], str], Callable[[], Awaitable[str]]], retry_times: int = 3) -> str:
    while retry_times >= 0:
        try:
            if callable(url):
                result = url()
                if asyncio.iscoroutine(result) or isinstance(result, Awaitable):
                    return await result
                return result
            elif isinstance(url, str):
                return url
        except Exception as e:
            retry_times -= 1
            if retry_times < 0:
                raise e
            await asyncio.sleep(2)
    raise RuntimeError("Max retries exceeded")