import asyncio
import os
import re
import math
from typing import Callable, Optional, Union, Awaitable

from typing_extensions import deprecated

import aiohttp
import aiofiles
import aiofiles.os as aio_os
from rich.progress import Progress
from aiohttp.client_exceptions import ClientPayloadError

from .misc import STATUS, StateManager

BLOCK_SIZE_REDUCTION_FACTOR = 0.75
MIN_BLOCK_SIZE = 2048


@deprecated("请使用 'download_file_multipart'")
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

    :param session: aiohttp.ClientSession 对象
    :param semaphore: 控制并发的信号量
    :param progress: 进度条对象
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
        progress.console.print(f"[yellow]{filename} 已经存在[/yellow]")
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
                            task_id = progress.add_task("download", filename=filename, total=total_size_in_bytes, completed=resume_from, status=STATUS.DOWNLOADING.value)
                        else:
                            progress.update(task_id, total=total_size_in_bytes, completed=resume_from, status=STATUS.DOWNLOADING.value, refresh=True)
                        
                        async with aiofiles.open(filename_downloading, 'ab') as f:
                            async for chunk in r.content.iter_chunked(block_size):
                                if chunk:
                                    await f.write(chunk)
                                    progress.update(task_id, advance=len(chunk))
                        
                        break 
            
            except Exception as e:
                if attempts_left > 0:
                    if task_id is not None:
                        progress.update(task_id, status=STATUS.RETRYING.value, refresh=True)
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
            progress.update(task_id, status=STATUS.FAILED.value, visible=False)

    finally:
        if await aio_os.path.exists(file_path):
            if task_id is not None:
                progress.update(task_id, status=STATUS.COMPLETED.value, visible=False)

            if callback:
                callback()

async def download_file_multipart(
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        progress: Progress,
        url: Union[str, Callable[[], str], Callable[[], Awaitable[str]]],
        dest_path: str,
        filename: str,
        retry_times: int = 3,
        chunk_size_mb: int = 10,
        headers: Optional[dict] = None,
        callback: Optional[Callable] = None,
):
    """
    下载文件

    :param session: aiohttp.ClientSession 对象
    :param semaphore: 控制并发的信号量
    :param progress: 进度条对象
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
        progress.console.print(f"[blue]{filename} 已经存在[/blue]")
        return

    part_paths = []
    part_expected_sizes = []
    task_id = None
    try:
        current_url = await fetch_url(url)

        async with session.head(current_url, headers=headers, allow_redirects=True) as response:
            response.raise_for_status()
            total_size = int(response.headers['Content-Length'])

        chunk_size = chunk_size_mb * 1024 * 1024
        num_chunks = math.ceil(total_size / chunk_size)

        tasks = []
        
        resumed_size = 0
        for i in range(num_chunks):
            part_path = os.path.join(dest_path, f"{filename}.{i + 1:03d}.downloading")
            part_paths.append(part_path)
            if await aio_os.path.exists(part_path):
                resumed_size += (await aio_os.stat(part_path)).st_size

        task_id = progress.add_task("download", filename=filename, status=STATUS.WAITING.value, total=total_size, completed=resumed_size)
        state_manager = StateManager(progress=progress, task_id=task_id)

        for i, start in enumerate(range(0, total_size, chunk_size)):
            end = min(start + chunk_size - 1, total_size - 1)
            part_expected_sizes.append(end - start + 1)

            task = _download_part(
                session=session,
                semaphore=semaphore,
                url=current_url,
                start=start,
                end=end,
                part_path=part_paths[i],
                state_manager=state_manager,
                headers=headers,
                retry_times=retry_times
            )
            tasks.append(task)
            
        await asyncio.gather(*tasks)

        assert len(part_paths) == len(part_expected_sizes)
        results = await asyncio.gather(*[_validate_part(part_paths[i], part_expected_sizes[i]) for i in range(num_chunks)])
        if all(results):
            await state_manager.request_status_update(part_id=StateManager.PARENT_ID, status=STATUS.MERGING)
            await _merge_parts(part_paths, filename_downloading)
            os.rename(filename_downloading, file_path)
        else:
            # 如果有任何一个分片校验失败，则视为下载失败
            await state_manager.request_status_update(part_id=StateManager.PARENT_ID, status=STATUS.FAILED)

    finally:
        if await aio_os.path.exists(file_path):
            if task_id is not None:
                await state_manager.request_status_update(part_id=StateManager.PARENT_ID, status=STATUS.COMPLETED)

            cleanup_tasks = [aio_os.remove(p) for p in part_paths if await aio_os.path.exists(p)]
            if cleanup_tasks:
                await asyncio.gather(*cleanup_tasks)
            if callback:
                callback()
        else:
            if task_id is not None:
                await state_manager.request_status_update(part_id=StateManager.PARENT_ID, status=STATUS.FAILED)

async def _download_part(
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        url: str,
        start: int,
        end: int,
        part_path: str,
        state_manager: StateManager,
        headers: Optional[dict] = None,
        retry_times: int = 3
):
    if headers is None:
        headers = {}
    
    local_headers = headers.copy()
    block_size = 8192
    attempts_left = retry_times + 1

    while attempts_left > 0:
        attempts_left -= 1
        
        try:
            resume_from = (await aio_os.path.getsize(part_path)) if await aio_os.path.exists(part_path) else 0
            
            if resume_from >= (end - start + 1):
                return

            current_start = start + resume_from
            local_headers['Range'] = f'bytes={current_start}-{end}'
            
            async with semaphore:
                async with session.get(url, headers=local_headers) as response:
                    response.raise_for_status()

                    await state_manager.request_status_update(part_id=start, status=STATUS.DOWNLOADING)

                    async with aiofiles.open(part_path, 'ab') as f:
                        async for chunk in response.content.iter_chunked(block_size):
                            if chunk:
                                await f.write(chunk)
                                state_manager.advance(len(chunk))
            return
        except Exception as e:
            if attempts_left > 0:
                await asyncio.sleep(3)
                await state_manager.request_status_update(part_id=start, status=STATUS.WAITING)
            else:
                # console.print(f"[red]分片 {os.path.basename(part_path)} 下载失败: {e}[/red]")
                await state_manager.request_status_update(part_id=start, status=STATUS.PARTIALLY_FAILED)

async def _validate_part(part_path: str, expected_size: int) -> bool:
    if not await aio_os.path.exists(part_path):
        return False
    actual_size = await aio_os.path.getsize(part_path)
    return actual_size == expected_size

async def _merge_parts(part_paths: list[str], final_path: str):
    async with aiofiles.open(final_path, 'wb') as final_file:
        try:
            for part_path in part_paths:
                async with aiofiles.open(part_path, 'rb') as part_file:
                    while True:
                        chunk = await part_file.read(8192)
                        if not chunk:
                            break
                        await final_file.write(chunk)
        except Exception as e:
            if aio_os.path.exists(final_path):
                await aio_os.remove(final_path)
            raise e



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