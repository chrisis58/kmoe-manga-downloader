from dataclasses import dataclass
from datetime import timedelta, timezone
from enum import Enum
from typing import Union

from typing_extensions import deprecated


class BASE_URL(Enum):
    @property
    @deprecated("KOX 已过时，请使用 KXO 或 KOZ。")
    def KOX(self) -> str:
        return "https://kox.moe"

    KXX = "https://kxx.moe"

    KXO = "https://kxo.moe"

    KOZ = "https://koz.moe"

    MOX = "https://mox.moe"

    @classmethod
    def alternatives(cls) -> set[str]:
        """返回备用的基础 URL 列表"""
        return {cls.KXO.value, cls.KOZ.value, cls.MOX.value}

    DEFAULT = KXX


@dataclass(frozen=True)
class _ApiRoute:
    PROFILE: str = "/my.php"
    """用户信息页面"""

    LOGIN: str = "/login.php"
    """登录页面"""

    LOGIN_DO: str = "/login_do.php"
    """登录接口"""

    MY_FOLLOW: str = "/myfollow.php"
    """关注列表页面"""

    BOOK_DATA: str = "/book_data.php"
    """书籍数据接口"""

    DOWNLOAD: str = "/dl/{book_id}/{volume_id}/1/{book_format}/{is_vip}/"
    """
    下载接口

    :param book_id: 书籍 ID
    :param volume_id: 卷 ID
    :param book_format: 书籍格式，1 表示 mobi，2 表示 epub
    :param is_vip: 是否为 VIP 书籍，1 表示是，0 表示否
    """

    GETDOWNURL: str = "/getdownurl.php?b={book_id}&v={volume_id}&mobi={book_format}&vip={is_vip}&json=1"
    """
    获取下载链接接口

    :param book_id: 书籍 ID
    :param volume_id: 卷 ID
    :param book_format: 书籍格式，1 表示 mobi，2 表示 epub
    :param is_vip: 是否为 VIP 书籍，1 表示是，0 表示否
    """


class LoginResponse(Enum):
    m100 = "登录成功。"

    e400 = "帳號或密碼錯誤。"
    e401 = "非法訪問，請使用瀏覽器正常打開本站。"
    e402 = "帳號已經註銷。不會解釋原因，無需提問。"
    e403 = "驗證失效，請刷新頁面重新操作。"

    unknown = "未知响应代码。"

    @classmethod
    def from_code(cls, code: str) -> "LoginResponse":
        return cls.__members__.get(code, cls.unknown)

    @classmethod
    def ok(cls, code: Union[str, "LoginResponse"]) -> bool:
        if isinstance(code, LoginResponse):
            return code == cls.m100
        return cls.from_code(code) == cls.m100


class BookFormat(Enum):
    EPUB = 2
    MOBI = 1

    @classmethod
    def from_name(cls, name: str) -> "BookFormat":
        ext = cls.__members__.get(name.upper())
        if ext is None:
            raise ValueError(f"未知的书籍格式：{name}")
        return ext


API_ROUTE = _ApiRoute()
"""API 路由常量实例"""

TIMEZONE = timezone(offset=timedelta(hours=8), name="Asia/Shanghai")
"""东八区为默认时区"""
