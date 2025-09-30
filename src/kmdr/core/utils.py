import functools
from typing import Optional, Callable
import asyncio

import aiohttp

import subprocess

from .structure import BookInfo, VolInfo
from .error import RedirectError


def singleton(cls):
    """
    **非线程安全**的单例装饰器
    """

    instances = {}

    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance

def construct_callback(callback: Optional[str]) -> Optional[Callable]:
    if callback is None or not isinstance(callback, str) or not callback.strip():
        return None

    def _callback(book: BookInfo, volume: VolInfo) -> int:
        nonlocal callback

        assert callback, "Callback script cannot be empty"
        formatted_callback = callback.strip().format(b=book, v=volume)

        return subprocess.run(formatted_callback, shell=True, check=True).returncode

    return _callback


def async_retry(
    attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    retry_on_status: set[int] = {500, 502, 503, 504, 429, 408},
    base_url_setter: Optional[Callable[[str], None]] = None,
):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            for attempt in range(attempts):
                try:
                    return await func(*args, **kwargs)
                except aiohttp.ClientResponseError as e:
                    if e.status in retry_on_status:
                        if attempt == attempts - 1:
                            raise
                    else:
                        raise
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    # 对于所有其他 aiohttp 客户端异常和超时，进行重试
                    if attempt == attempts - 1:
                        raise
                except RedirectError as e:
                    if base_url_setter:
                        base_url_setter(e.new_base_url)
                        print(f"检测到重定向，已自动更新 base url 为: {e.new_base_url}。立即重试...")
                        continue
                    else:
                        raise
                
                await asyncio.sleep(current_delay)

                current_delay *= backoff
        return wrapper
    return decorator
