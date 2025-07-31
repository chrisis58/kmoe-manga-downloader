from typing import Callable, Optional
import os
import time

from requests import Session, HTTPError
from requests.exceptions import ChunkedEncodingError
from tqdm import tqdm
import re

def download_file(
            session: Session, 
            url: str,
            dest_path: str, 
            filename: str, 
            retry_times: int = 0, 
            headers: Optional[dict] = None, 
            callback: Optional[Callable] = None,
    ):
    if headers is None:
        headers = {}
    filename_downloading = f'{filename}.downloading'
        
    file_path = f'{dest_path}/{filename}'
    tmp_file_path = f'{dest_path}/{filename_downloading}'
    
    if not os.path.exists(dest_path):
        os.makedirs(dest_path, exist_ok=True)
        
    if os.path.exists(file_path):
        tqdm.write(f"{filename} already exists")
        return

    resume_from = 0
    total_size_in_bytes = 0
    
    if os.path.exists(tmp_file_path):
        resume_from = os.path.getsize(tmp_file_path)
    
    if resume_from:
        headers['Range'] = f'bytes={resume_from}-'

    block_size = 8192
        
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
        tqdm.write(f"{type(e).__name__} occurred while downloading {filename}. ", end='')

        if isinstance(e, HTTPError):
            e.request.headers['Cookie'] = '***MASKED***'
            tqdm.write(f"Request Headers: {e.request.headers}")
            tqdm.write(f"Response Headers: {e.response.headers}")

        if isinstance(e, ChunkedEncodingError):
            block_size = max(block_size // 4 * 3, 2048)

        if retry_times > 0:
            # 重试下载
            tqdm.write(f"Retry after 3 seconds...")
            time.sleep(3) # 等待3秒后重试，避免触发限流
            download_file(session, url, dest_path, filename, retry_times - 1, headers, callback)
        else:
            tqdm.write(f"\nMeet max retry times, download failed")
            raise e

def safe_filename(name: str) -> str:
    """
    替换非法文件名字符为下划线
    """
    return re.sub(r'[\\/:*?"<>|]', '_', name)


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
    cache = {}

    def wrapper(*args, **kwargs):
        if not kwargs:
            return func(*args, **kwargs)
        
        nonlocal cache

        key = frozenset(kwargs.items())

        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]

    return wrapper
