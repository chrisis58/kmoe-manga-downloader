import functools
from typing import Optional, Callable

from requests import Session
import threading
import subprocess

from .structure import BookInfo, VolInfo

_session_instance: Optional[Session] = None

_session_lock = threading.Lock()

HEADERS = {
    'User-Agent': 'kmdr/1.0 (https://github.com/chrisis58/kmoe-manga-downloader)'
}

def get_singleton_session() -> Session:
    global _session_instance

    if _session_instance is None:
        with _session_lock:
            if _session_instance is None:
                _session_instance = Session()
                _session_instance.headers.update(HEADERS)

    return _session_instance

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
