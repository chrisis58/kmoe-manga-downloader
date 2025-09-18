import functools
from typing import Optional, Callable
import asyncio

import aiohttp

from deprecation import deprecated
from requests import Session
import threading
import subprocess

from .structure import BookInfo, VolInfo

_session_instance: Optional[Session] = None

_session_lock = threading.Lock()

HEADERS = {
    'User-Agent': 'kmdr/1.0 (https://github.com/chrisis58/kmoe-manga-downloader)'
}

@deprecated(details="在 asyncio 环境中请使用 'session_var' 来管理 session")
def get_singleton_session() -> Session:
    global _session_instance

    if _session_instance is None:
        with _session_lock:
            if _session_instance is None:
                _session_instance = Session()
                _session_instance.headers.update(HEADERS)

    return _session_instance

@deprecated(details="在 asyncio 环境中请使用 'session_var' 来管理 session")
def clear_session_context():
    session = get_singleton_session()
    session.proxies.clear()
    session.headers.clear()
    session.cookies.clear()
    session.headers.update(HEADERS)

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

@deprecated()
def no_proxy(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        session = get_singleton_session()

        cached_proxies = session.proxies.copy()
        session.proxies.clear()

        try:
            return func(*args, **kwargs)
        finally:
            session.proxies = cached_proxies

    return wrapper


def async_retry(
    attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    retry_on_status: set[int] = {500, 502, 503, 504, 429, 408}
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
                
                await asyncio.sleep(current_delay)

                current_delay *= backoff
        return wrapper
    return decorator