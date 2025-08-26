from typing import Callable, Optional, Union
import os
import time
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
            retry_times: int = 0, 
            headers: Optional[dict] = None, 
            callback: Optional[Callable] = None,
            block_size: int = 8192
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
    :param block_size: 块大小
    """
    if headers is None:
        headers = {}
    filename_downloading = f'{filename}.downloading'

    file_path = f'{dest_path}/{filename}'
    tmp_file_path = f'{dest_path}/{filename_downloading}'
    
    if not os.path.exists(dest_path):
        os.makedirs(dest_path, exist_ok=True)
        
    if os.path.exists(file_path):
        tqdm.write(f"{filename} already exists.")
        return

    resume_from = 0
    total_size_in_bytes = 0
    
    if os.path.exists(tmp_file_path):
        resume_from = os.path.getsize(tmp_file_path)
    
    if resume_from:
        headers['Range'] = f'bytes={resume_from}-'

    if callable(url):
        url = url()

    try:
        with session.get(url = url, stream=True, headers=headers) as r:
            r.raise_for_status()
            
            total_size_in_bytes = int(r.headers.get('content-length', 0)) + resume_from
            
            with open(tmp_file_path, 'ab') as f:
                with tqdm(total=total_size_in_bytes, unit='B', unit_scale=True, desc=f'{filename}', initial=resume_from) as progress_bar:
                    for chunk in r.iter_content(chunk_size=block_size):
                        if chunk:
                            f.write(chunk)
                            progress_bar.update(len(chunk))
            
            if (os.path.getsize(tmp_file_path) == total_size_in_bytes):
                os.rename(tmp_file_path, file_path)
                
                if callback:
                    callback()
    except Exception as e:
        prefix = f"{type(e).__name__} occurred while downloading {filename}. "

        new_block_size = block_size
        if isinstance(e, ChunkedEncodingError):
            new_block_size = max(int(block_size * BLOCK_SIZE_REDUCTION_FACTOR), MIN_BLOCK_SIZE)

        if retry_times > 0:
            # 重试下载
            tqdm.write(f"{prefix} Retry after 3 seconds...")
            time.sleep(3) # 等待3秒后重试，避免触发限流
            download_file(session, url, dest_path, filename, retry_times - 1, headers, callback, new_block_size)
        else:
            tqdm.write(f"{prefix} Meet max retry times, download failed.")
            raise e

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