import asyncio
import os
import re
import math
from typing import Callable, Optional, Union, Awaitable, Tuple
import shutil

from typing_extensions import deprecated

import aiohttp
import aiofiles
import aiofiles.os as aio_os
from rich.progress import Progress
from aiohttp.client_exceptions import ClientPayloadError

from kmdr.core.console import info, log, debug
from kmdr.core.error import RangeNotSupportedError
from kmdr.core.utils import async_retry, sanitize_headers

from .misc import STATUS, StateManager

CONTENT_RANGE_PATTERN = re.compile(r'bytes\s+(\d+)-(\d+)/(\d+|\*)', re.IGNORECASE)
"""用于解析 Content-Range 头的正则表达式模式。"""

BLOCK_SIZE_REDUCTION_FACTOR = 0.75
MIN_BLOCK_SIZE = 2048

_HEAD_SEMAPHORE_VALUE = 3
_HEAD_SEMAPHORE: Optional[asyncio.Semaphore] = None
"""定义的用于 HEAD 请求的信号量，限制并发数量以避免触发服务器限流。"""

def _get_head_request_semaphore() -> asyncio.Semaphore:
    """惰性初始化 HEAD 请求信号量。"""
    global _HEAD_SEMAPHORE
    
    if _HEAD_SEMAPHORE is None:
        _HEAD_SEMAPHORE = asyncio.Semaphore(_HEAD_SEMAPHORE_VALUE)
    return _HEAD_SEMAPHORE


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
        task_id = None,
        resumable: bool = True,
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
        info(f"[yellow]{filename} 已经存在[/yellow]")
        return

    log("开始下载文件:", filename, "到路径:", dest_path)

    block_size = 8192
    attempts_left = retry_times + 1

    while attempts_left > 0:
        attempts_left -= 1
        
        resume_from = (await aio_os.stat(filename_downloading)).st_size \
            if resumable and await aio_os.path.exists(filename_downloading) \
            else 0

        if resumable and resume_from > 0:
            headers = headers.copy()
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
                        progress.update(task_id, total=total_size_in_bytes, completed=resume_from, status=STATUS.DOWNLOADING.value)
                    
                    mode = 'ab' if resumable and resume_from > 0 else 'wb'
                    async with aiofiles.open(filename_downloading, mode) as f:
                        async for chunk in r.content.iter_chunked(block_size):
                            if chunk:
                                await f.write(chunk)
                                progress.update(task_id, advance=len(chunk))
                    
            await aio_os.rename(filename_downloading, file_path)
            break

        except (asyncio.CancelledError, KeyboardInterrupt):
            # 如果任务被取消，更新状态为已取消
            if task_id is not None:
                progress.update(task_id, status=STATUS.CANCELLED.value)
            raise
        
        except Exception as e:
            if attempts_left > 0:
                log("正在重试... 剩余重试次数:", attempts_left)
                debug("下载出错:", e, "，正在重试... 剩余重试次数:", attempts_left)
                if task_id is not None:
                    progress.update(task_id, status=STATUS.RETRYING.value)
                if isinstance(e, ClientPayloadError):
                    new_block_size = max(int(block_size * BLOCK_SIZE_REDUCTION_FACTOR), MIN_BLOCK_SIZE)
                    if new_block_size < block_size:
                        block_size = new_block_size
                await asyncio.sleep(3)
            else:
                if task_id is not None:
                    progress.update(task_id, status=STATUS.FAILED.value)
                raise e

        finally:
            if await aio_os.path.exists(file_path):
                if task_id is not None:
                    progress.update(task_id, status=STATUS.COMPLETED.value)

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
        info(f"[blue]{filename} 已经存在[/blue]")
        return

    log("开始下载文件:", filename)
    part_paths = []
    part_expected_sizes = []
    task_id = None

    state_manager: Optional[StateManager] = None
    try:
        async with _get_head_request_semaphore():
            # 获取文件信息，请求以获取文件大小
            # 控制并发，避免过多并发请求触发服务器限流
            current_url = await fetch_url(url)
            total_size = await _fetch_content_length(session, current_url, headers=headers)

        chunk_size = determine_chunk_size(file_size=total_size, base_chunk_mb=chunk_size_mb)
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
        results = await asyncio.gather(*[
            asyncio.to_thread(_sync_validate_part, part_paths[i], part_expected_sizes[i]) 
            for i in range(num_chunks)
        ])
        if all(results):
            await state_manager.request_status_update(part_id=StateManager.PARENT_ID, status=STATUS.MERGING)
            await asyncio.to_thread(_sync_merge_parts, part_paths, filename_downloading)
            await aio_os.rename(filename_downloading, file_path)
        else:
            # 如果有任何一个分片校验失败，则视为下载失败
            await state_manager.request_status_update(part_id=StateManager.PARENT_ID, status=STATUS.FAILED)
    
    except RangeNotSupportedError:

        # 尝试清理临时文件
        state_manager = None
        cleanup_tasks = []
        for part_path in part_paths:
            if await aio_os.path.exists(part_path):
                cleanup_tasks.append(aio_os.remove(part_path))
        if await aio_os.path.exists(filename_downloading):
            cleanup_tasks.append(aio_os.remove(filename_downloading))

        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks)

        debug("服务器不支持分片下载，使用普通下载方式")
        await download_file(
            session=session,
            semaphore=semaphore,
            progress=progress,
            url=url,
            dest_path=dest_path,
            filename=filename,
            retry_times=retry_times,
            headers=headers,
            callback=callback,
            task_id=task_id,
            resumable=False
        )

    finally:
        if await aio_os.path.exists(file_path):
            if task_id is not None and state_manager is not None:
                await state_manager.request_status_update(part_id=StateManager.PARENT_ID, status=STATUS.COMPLETED)

            cleanup_tasks = [aio_os.remove(p) for p in part_paths if await aio_os.path.exists(p)]
            if cleanup_tasks:
                await asyncio.gather(*cleanup_tasks)
            if callback:
                callback()
        else:
            if task_id is not None and state_manager is not None:
                await state_manager.request_status_update(part_id=StateManager.PARENT_ID, status=STATUS.FAILED)

@async_retry()
async def _fetch_content_length(
        session: aiohttp.ClientSession,
        url: str,
        headers: Optional[dict] = None,
) -> int:
    """
    获取文件的内容长度（字节数）

    :note: 这个请求完成后，服务器就会记录这次下载，并消耗对应的流量配额，详细的规则请参考网站说明：
    - 注 1 : 訂閱連載中的漫畫，有更新時自動推送的卷(冊)，暫不計算在使用額度中，不扣減使用額度。
    - 注 2 : 對同一卷(冊)書在 12 小時內重複*下載*，不會重複扣減額度。但重復推送是會扣減的。

    :param session: aiohttp.ClientSession 对象
    :param url: 文件 URL
    :param headers: 请求头
    :return: 文件大小（字节数）
    """
    if headers is None:
        headers = {}
    
    probe_headers = headers.copy()
    probe_headers['Range'] = 'bytes=0-0'

    async with session.get(url, headers=probe_headers, allow_redirects=True) as response:
        # 普通下载链接可能不支持 HEAD 请求，尝试使用 GET 请求获取文件大小
        # see: https://github.com/chrisis58/kmoe-manga-downloader/issues/25
        response.raise_for_status()

        debug("请求响应状态码:", response.status)
        debug("请求头:", sanitize_headers(response.request_info.headers))
        debug("响应头:", sanitize_headers(response.headers))
        
        if 'Content-Range' not in response.headers:
            raise RangeNotSupportedError("响应头中缺少 Content-Range。")

        cr = response.headers['Content-Range']
        start, end, total_size = resolve_content_range(cr)
        debug("解析 Content-Range:", cr, "得到 start:", start, "end:", end, "total_size:", total_size)

        if total_size is None:
            raise RangeNotSupportedError("服务器未提供完整的文件大小信息。", content_range=cr)

        if start != 0 or end != 0:
            raise RangeNotSupportedError("服务器不支持范围请求，无法进行分片下载。", content_range=cr)

        return total_size

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
                debug("开始下载分片:", os.path.basename(part_path), "范围:", current_start, "-", end)
                async with session.get(url, headers=local_headers) as response:
                    response.raise_for_status()
                    await state_manager.request_status_update(part_id=start, status=STATUS.DOWNLOADING)

                    async with aiofiles.open(part_path, 'ab') as f:
                        async for chunk in response.content.iter_chunked(block_size):
                            if chunk:
                                await f.write(chunk)
                                state_manager.advance(len(chunk))
                await state_manager.pop_part(part_id=start)
                log("分片", os.path.basename(part_path), "下载完成。")
            return
        
        except RangeNotSupportedError:
            raise
    
        except asyncio.CancelledError:
            # 如果任务被取消，更新状态为已取消
            await state_manager.request_status_update(part_id=start, status=STATUS.CANCELLED)
            raise

        except Exception as e:
            if attempts_left > 0:
                debug("分片", os.path.basename(part_path), "下载出错:", e, "，正在重试... 剩余重试次数:", attempts_left)
                await state_manager.request_status_update(part_id=start, status=STATUS.WAITING)
                await asyncio.sleep(3)
            else:
                # console.print(f"[red]分片 {os.path.basename(part_path)} 下载失败: {e}[/red]")
                debug("分片", os.path.basename(part_path), "下载失败:", e)
                await state_manager.request_status_update(part_id=start, status=STATUS.PARTIALLY_FAILED)

def _sync_validate_part(part_path: str, expected_size: int) -> bool:
    """
    使用同步的 IO 来验证分片文件的完整性。

    :param part_path: 分片文件路径
    :param expected_size: 预期的文件大小
    :return: 如果文件大小匹配则返回 True，否则返回 False
    :note: 这个函数应该在线程池中运行。
    :usage: await asyncio.to_thread(_sync_validate_part, part_path, expected_size)
    """
    if not os.path.exists(part_path):
        return False
    actual_size = os.path.getsize(part_path)
    return actual_size == expected_size

def _sync_merge_parts(part_paths: list[str], final_path: str):
    """
    使用同步的 IO 来合并文件。

    :param part_paths: 分片文件路径列表
    :param final_path: 最终合并后的文件路径
    :note: 这个函数应该在线程池中运行。
    :usage: await asyncio.to_thread(_sync_merge_parts, part_paths, final_path)
    """
    debug("合并分片到最终文件:", final_path)
    try:
        with open(final_path, 'wb') as final_file:
            for part_path in part_paths:
                with open(part_path, 'rb') as part_file:
                    shutil.copyfileobj(part_file, final_file)
    except Exception as e:
        if os.path.exists(final_path):
            os.remove(final_path)
        raise e


def determine_chunk_size(
        file_size: int, 
        base_chunk_mb: int = 10,
        max_chunks_limit: int = 100,
        min_chunk_threshold_factor: float = 0.2
) -> int:
    """
    计算合适的分片大小以优化下载性能。

    TODO: 这个算法可以进一步优化，例如考虑网络状况、服务器限制等因素。10 这个魔法数字也许可以调整。
    需要收集更多的信息：
    - 文件大小的分布
    - 用户的下载速度分布
    - 连接开销的大致值

    :param file_size: 文件总大小（字节）
    :param base_chunk_mb: 基础分片大小 (MB)
    :param max_chunks_limit: 限制的最大分片数
    :param min_chunk_threshold_factor: 最小分片的体积因子
    :return: 最佳的每个分片的大小（字节）
    """
    base_chunk = int(base_chunk_mb * 1024 * 1024)

    if not isinstance(file_size, int) or file_size <= 0:
        # 如果文件大小不正常，返回基础分片大小
        return base_chunk

    if file_size <= base_chunk * (1 + min_chunk_threshold_factor):
        # 如果文件较小，直接使用单分片下载，避免无谓的分片开销 
        # 例如 10.2MB 会被视为单分片下载
        return file_size

    num_chunks = math.ceil(file_size / base_chunk)

    if num_chunks > max_chunks_limit:
        # 如果文件太大导致分片数量过多 (2GB -> 200 块)
        # 增加分片大小，将分片数限制在 100
        return int(math.ceil(file_size / max_chunks_limit))

    # 计算最后一个分片的大小，如果过小则调整分片大小
    # 例如 250.2MB - (10MB * (26 - 1)) = 0.2MB
    last_chunk_size = file_size - (base_chunk * (num_chunks - 1))

    if last_chunk_size < base_chunk * min_chunk_threshold_factor:
        # 如果最后一个分片过小，则均摊到前面的分片中
        # 例如 250.2 / 25 = 10.008MB
        return int(math.ceil(file_size / (num_chunks - 1)))
    else:
        return base_chunk

CHAR_MAPPING = {
    '\\': '＼',
    '/': '／',
    ':': '：',
    '*': '＊',
    '?': '？',
    '"': '＂',
    '<': '＜',
    '>': '＞',
    '|': '｜',
}
DEFAULT_ILLEGAL_CHARS_REPLACEMENT = '_'
ILLEGAL_CHARS_RE = re.compile(r'[\\/:*?"<>|]')

def readable_safe_filename(name: str) -> str:
    """
    将字符串转换为安全的文件名，替换掉非法字符。
    """
    def replace_char(match):
        char = match.group(0)
        return CHAR_MAPPING.get(char, DEFAULT_ILLEGAL_CHARS_REPLACEMENT)

    return ILLEGAL_CHARS_RE.sub(replace_char, name).strip()

@deprecated("请使用 'readable_safe_filename'")
def safe_filename(name: str) -> str:
    """
    替换非法文件名字符为下划线
    """
    return re.sub(r'[\\/:*?"<>|]', '_', name)

async def fetch_url(url: Union[str, Callable[[], str], Callable[[], Awaitable[str]]]) -> str:
    """
    获取下载链接的包装函数，支持直接传入字符串或异步/同步的 Supplier 函数。

    :note: 不包含重试机制，调用方需自行处理。
    :param url: 下载链接或其 Supplier
    :return: 下载链接
    """

    if callable(url):
        result = url()
        if asyncio.iscoroutine(result) or isinstance(result, Awaitable):
            # 如果 url() 是一个异步函数，等待它
            return await result
        # 如果 url() 是一个同步函数，直接返回
        return result
    elif isinstance(url, str):
        # 如果 url 只是个字符串，直接返回
        return url

def resolve_content_range(
        content_range_header: Optional[str],
) -> Tuple[int, int, Optional[int]]:
    """
    解析 Content-Range 头以获取文件的起始字节、结束字节和总大小。

    :param content_range_header: Content-Range 头
    :return: (start, end, total)
    :raises RangeNotSupportedError: 如果无法解析 Content-Range 头
    """
    if not content_range_header:
        raise RangeNotSupportedError("缺少 Content-Range 头", content_range="N/A")

    match = CONTENT_RANGE_PATTERN.search(content_range_header)
    if not match:
        raise RangeNotSupportedError("无法解析 Content-Range 头", content_range=content_range_header)

    start_str, end_str, total_size_str = match.group(1), match.group(2), match.group(3)

    total_size = int(total_size_str) if total_size_str != '*' else None
    
    return int(start_str), int(end_str), total_size
