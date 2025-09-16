import asyncio
import os
from typing import Callable, Optional, Union, List
import math

import aiohttp
import aiofiles
import aiofiles.os as aio_os
from tqdm.asyncio import tqdm

async def download_file_multipart(
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        url: Union[str, Callable[[], str]],
        dest_path: str,
        filename: str,
        retry_times: int = 3,
        chunk_size_mb: int = 10,
        headers: Optional[dict] = None,
        callback: Optional[Callable] = None,
):
    if headers is None:
        headers = {}
        
    file_path = os.path.join(dest_path, filename)
    filename_downloading = f'{file_path}.downloading'
    
    if not await aio_os.path.exists(dest_path):
        await aio_os.makedirs(dest_path, exist_ok=True)

    if await aio_os.path.exists(file_path):
        tqdm.write(f"{filename} 已经存在")
        return

    part_paths = []
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
        
        progress_bar = tqdm(total=total_size, initial=resumed_size, unit='B', unit_scale=True, desc=filename, leave=False, dynamic_ncols=True)

        for i, start in enumerate(range(0, total_size, chunk_size)):
            end = min(start + chunk_size - 1, total_size - 1)

            task = _download_part(
                session=session,
                semaphore=semaphore,
                url=current_url,
                start=start,
                end=end,
                part_path=part_paths[i],
                progress_bar=progress_bar,
                headers=headers,
                retry_times=retry_times
            )
            tasks.append(task)
            
        await asyncio.gather(*tasks)
        
        progress_bar.set_description(f"{filename} (合并中...)")
        await _merge_parts(part_paths, filename_downloading)
        
        os.rename(filename_downloading, file_path)
    except Exception as e:
        tqdm.write(f"下载 {filename} 失败: {e}")
    finally:
        if await aio_os.path.exists(file_path):
            # 成功下载
            progress_bar.close()
            tqdm.write(f"{filename} 下载完成")
            await asyncio.gather(*[aio_os.remove(p) for p in part_paths if await aio_os.path.exists(p)])

            if callback:
                callback()

async def _download_part(
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        url: str,
        start: int,
        end: int,
        part_path: str,
        progress_bar: tqdm,
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
                    
                    async with aiofiles.open(part_path, 'ab') as f:
                        async for chunk in response.content.iter_chunked(block_size):
                            if chunk:
                                await f.write(chunk)
                                progress_bar.update(len(chunk))
            
            return

        except Exception as e:
            if attempts_left > 0:
                await asyncio.sleep(3)
            else:
                progress_bar.write(f"分片 {part_path} 下载失败: {e}")
                raise


async def _merge_parts(part_paths: List[str], final_path: str):
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
            if os.path.exists(final_path):
                os.remove(final_path)
            raise e

async def fetch_url(url: Union[str, Callable[[], str]], retry_times: int = 3) -> str:
    while retry_times >= 0:
        try:
            if asyncio.iscoroutinefunction(url):
                return await url()
            elif callable(url):
                return url()
            else:
                return url
        except Exception as e:
            retry_times -= 1
            if retry_times < 0:
                raise e
            await asyncio.sleep(2)
