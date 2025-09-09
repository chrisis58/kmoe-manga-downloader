from typing import Callable, Optional, Union
import os
import time
import threading
from functools import wraps

from requests import Session, HTTPError
from requests.exceptions import ChunkedEncodingError
from tqdm import tqdm
import re

BLOCK_SIZE_REDUCTION_FACTOR = 0.75
MIN_BLOCK_SIZE = 2048

def download_file(
        session: Session,
        url: Union[str, Callable[[], str]],
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
    filename_downloading = f'{filename}.downloading'
    file_path = os.path.join(dest_path, filename)
    tmp_file_path = os.path.join(dest_path, filename_downloading)

    if not os.path.exists(dest_path):
        os.makedirs(dest_path, exist_ok=True)

    if os.path.exists(file_path):
        tqdm.write(f"{filename} 已经存在")
        return

    block_size = 8192
    
    attempts_left = retry_times + 1
    progress_bar = tqdm(
        total=0, unit='B', unit_scale=True,
        desc=f'{filename} (连接中...)',
        leave=False,
        dynamic_ncols=True
    )

    try:
        while attempts_left > 0:
            attempts_left -= 1
            
            resume_from = os.path.getsize(tmp_file_path) if os.path.exists(tmp_file_path) else 0
            
            if resume_from:
                headers['Range'] = f'bytes={resume_from}-'

            try:
                current_url = url() if callable(url) else url
                with session.get(url=current_url, stream=True, headers=headers) as r:
                    r.raise_for_status()

                    total_size_in_bytes = int(r.headers.get('content-length', 0)) + resume_from

                    progress_bar.set_description(f'{filename}')
                    progress_bar.total = total_size_in_bytes
                    progress_bar.n = resume_from
                    progress_bar.refresh()

                    with open(tmp_file_path, 'ab') as f:
                        for chunk in r.iter_content(chunk_size=block_size):
                            if chunk:
                                f.write(chunk)
                                progress_bar.update(len(chunk))

                    if os.path.getsize(tmp_file_path) >= total_size_in_bytes:
                        os.rename(tmp_file_path, file_path)
                        if callback:
                            callback()
                        return

            except Exception as e:
                if attempts_left > 0:
                    progress_bar.set_description(f'{filename} (重试中...)')
                    if isinstance(e, ChunkedEncodingError):
                        new_block_size = max(int(block_size * BLOCK_SIZE_REDUCTION_FACTOR), MIN_BLOCK_SIZE)
                        if new_block_size < block_size:
                            block_size = new_block_size

                    # 避免限流
                    time.sleep(3)
                else:
                    raise e
    finally:
        if progress_bar.total and progress_bar.n >= progress_bar.total:
            tqdm.write(f"{filename} 下载完成")
        elif progress_bar.total is not None:
            tqdm.write(f"{filename} 下载失败")
        progress_bar.close()


def safe_filename(name: str) -> str:
    """
    替换非法文件名字符为下划线
    """
    return re.sub(r'[\\/:*?"<>|]', '_', name)


function_cache = {}

def cached_by_kwargs(func):
    """
    根据关键字参数缓存函数结果的装饰器。

    Example:
    >>> @kwargs_cached
    >>> def add(a, b, c):
    >>>     return a + b + c
    >>> result1 = add(1, 2, c=3)  # Calls the function
    >>> result2 = add(3, 2, c=3)  # Uses cached result
    >>> assert result1 == result2  # Both results are the same
    """

    global function_cache
    if func not in function_cache:
        function_cache[func] = {}

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not kwargs:
            return func(*args, **kwargs)

        key = frozenset(kwargs.items())

        if key not in function_cache[func]:
            function_cache[func][key] = func(*args, **kwargs)
        return function_cache[func][key]

    return wrapper

def clear_cache(func):
    assert hasattr(func, "__wrapped__"), "Function is not wrapped"
    global function_cache

    wrapped = func.__wrapped__

    if wrapped in function_cache:
        function_cache[wrapped] = {}
