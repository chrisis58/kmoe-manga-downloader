from dataclasses import dataclass
from enum import Enum
from typing import Union

from typing_extensions import deprecated

class BASE_URL(Enum):

    @property
    @deprecated("KOX 已过时，请使用 KXO 或 KOZ。")
    def KOX(self) -> str:
        return 'https://kox.moe'
    
    KXX = 'https://kxx.moe'

    KXO = 'https://kxo.moe'

    KOZ = 'https://koz.moe'

    MOX = 'https://mox.moe'

    @classmethod
    def alternatives(cls) -> set[str]:
        """返回备用的基础 URL 列表"""
        return {cls.KXO.value, cls.KOZ.value, cls.MOX.value}

    DEFAULT = KXX

@dataclass(frozen=True)
class _ApiRoute():
    PROFILE: str = '/my.php'
    """用户信息页面"""

    LOGIN: str = '/login.php'
    """登录页面"""

    LOGIN_DO: str = '/login_do.php'
    """登录接口"""

    MY_FOLLOW: str = '/myfollow.php'
    """关注列表页面"""

    BOOK_DATA: str = '/book_data.php'
    """书籍数据接口"""

    DOWNLOAD: str = '/dl/{book_id}/{volume_id}/1/2/{is_vip}/'
    """下载接口"""

    GETDOWNURL: str = '/getdownurl.php?b={book_id}&v={volume_id}&mobi=2&vip={is_vip}&json=1'
    """获取下载链接接口"""


class LoginResponse(Enum):
    m100 = "登录成功。"

    e400 = "帳號或密碼錯誤。"
    e401 = "非法訪問，請使用瀏覽器正常打開本站。"
    e402 = "帳號已經註銷。不會解釋原因，無需提問。"
    e403 = "驗證失效，請刷新頁面重新操作。"

    unknown = "未知响应代码。"

    @classmethod
    def from_code(cls, code: str) -> 'LoginResponse':
        return cls.__members__.get(code, cls.unknown)

    @classmethod
    def ok(cls, code: Union[str, 'LoginResponse']) -> bool:
        if isinstance(code, LoginResponse):
            return code == cls.m100
        return cls.from_code(code) == cls.m100

API_ROUTE = _ApiRoute()
"""API 路由常量实例"""
