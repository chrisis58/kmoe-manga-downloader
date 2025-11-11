import functools
from typing import Optional, Callable, TypeVar, Hashable, Generic, Mapping, Any
import asyncio
from asyncio.proactor_events import _ProactorBasePipeTransport
import random

import aiohttp

import subprocess

from .structure import BookInfo, VolInfo
from .error import RedirectError
from .protocol import Consumer
from .console import debug


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
    base_url_setter: Optional[Consumer[str]] = None,
    on_failure: Optional[Callable[[Exception], None]] = None
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
                        debug("检测到重定向，已自动更新 base url 为", e.new_base_url)
                        continue
                    else:
                        raise
                except Exception as e:
                    if on_failure:
                        on_failure(e)
                        break
                    else:
                        raise
                
                await asyncio.sleep(current_delay)

                current_delay *= backoff
        return wrapper
    return decorator


H = TypeVar('H', bound=Hashable)
class PrioritySorter(Generic[H]):
    """
    根据优先级对元素进行排序的工具类
    """

    DEFAULT_ORDER = 10

    def __init__(self):
        self._items: dict[H, int] = {}

    def __repr__(self) -> str:
        return f"PrioritySorter({self._items})"

    def get(self, key: H) -> Optional[int]:
        """获取对应元素的优先级"""
        return self._items.get(key)

    def set(self, key: H, value: int = DEFAULT_ORDER) -> None:
        """设置对应元素的优先级"""
        self._items[key] = value

    def remove(self, key: H) -> None:
        """移除对应元素"""
        self._items.pop(key, None)

    def incr(self, key: H, offset: int = 1) -> None:
        """提升对应元素的优先级"""
        current_value = self._items.get(key, self.DEFAULT_ORDER)
        self._items[key] = current_value + offset

    def decr(self, key: H, offset: int = 1) -> None:
        """降低对应元素的优先级"""
        current_value = self._items.get(key, self.DEFAULT_ORDER)
        self._items[key] = current_value - offset

    def sort(self) -> list[H]:
        """返回根据优先级排序后的元素列表，优先级高的元素排在前面"""
        return [k for k, v in sorted(self._items.items(), key=lambda item: item[1], reverse=True)]
    
def _silence_event_loop_closed(func):
    """
    用于静默处理 'Event loop is closed' 异常的装饰器。
    该异常在某些情况下（如 Windows 平台使用 Proactor 事件循环）会在对象销毁时抛出，
    导致程序输出不必要的错误信息。此装饰器捕获该异常并忽略它。
    
    @see https://github.com/aio-libs/aiohttp/issues/4324
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except RuntimeError as e:
            if str(e) != 'Event loop is closed':
                raise
 
    return wrapper

_ProactorBasePipeTransport.__del__ = _silence_event_loop_closed(_ProactorBasePipeTransport.__del__)



SENSITIVE_KEYS = {'cookie', 'authorization', 'proxy-authorization', 'set-cookie'}
"""定义需要脱敏的字段（全部小写以便不区分大小写匹配）"""

def sanitize_headers(headers: Mapping[str, Any]) -> dict:
    """
    清洗 HTTP 头信息，隐藏敏感字段（如 Cookie, Authorization）。
    """
    return {
        k: '******' if k.lower() in SENSITIVE_KEYS else v
        for k, v in headers.items()
    }

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
]

def get_random_ua() -> str:
    """
    从池中随机选择一个 UA
    """
    return random.choice(USER_AGENTS)
