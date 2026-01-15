from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Optional

class VolumeType(Enum):
    VOLUME = "單行本"
    EXTRA = "番外篇"
    SERIALIZED = "連載話"

@dataclass(frozen=True)
class VolInfo:
    """
    Kmoe 卷信息
    """

    id: str

    extra_info: str
    """
    额外信息
    - 0: 无
    - 1: 最近一週更新
    - 2: 90天內曾下載/推送
    """

    is_last: bool

    vol_type: VolumeType

    index: int
    """
    从1开始的卷索引
    如果卷类型为「連載話」，则表示起始话数
    """

    name: str

    pages: int

    size: float
    """
    卷大小，单位为MB
    """


@dataclass(frozen=True)
class BookInfo:
    id: str
    name: str
    url: str
    author: str
    status: str
    last_update: str

@dataclass
class Config:

    option: Optional[dict] = None
    """
    用来存储下载相关的配置选项
    - retry_times: 重试次数
    - dest: 下载文件保存路径
    - callback: 下载完成后的回调函数
    - proxy: 下载时使用的代理
    - num_workers: 下载时使用的线程数
    """

    cookie: Optional[dict[str, str]] = None

    base_url: Optional[str] = None

    cred_pool: Optional[list['Credential']] = None
    """
    凭证池，存储多个账号的凭证信息
    """

class CredentialStatus(Enum):
    ACTIVE = "active"
    """标记凭证为正常状态"""

    INVALID = "invalid"
    """标记凭证为无效状态"""

    QUOTA_EXCEEDED = "quota_exceeded"
    """标记凭证为流量用尽状态"""

    DISABLED = "disabled"
    """标记凭证为禁用状态"""

    TEMPORARILY = "temporarily"
    """标记凭证为临时的状态"""

@dataclass
class QuotaInfo:

    reset_day: int
    """
    流量重置日, 当日 0 点重置
    """

    total: float
    used: float

    reserved: float = 0.0
    unsynced_usage: float = 0.0

    update_at: float = field(default_factory=time.time)

    @property
    def remaining(self) -> float:
        real_remaining = self.total - self.used - self.reserved
        return max(0.0, real_remaining)

    def reserve(self, amount: float) -> bool:
        if self.remaining >= amount:
            self.reserved += amount
            return True
        return False

@dataclass
class Credential:

    username: str
    """
    账号用户名，用作唯一标识
    """

    cookies: dict[str, str]

    user_quota: QuotaInfo

    level: int

    nickname: Optional[str] = None

    vip_quota: Optional[QuotaInfo] = None

    order: int = 0

    status: CredentialStatus = CredentialStatus.ACTIVE

    note: Optional[str] = None

    @property
    def is_vip(self) -> bool:
        return self.vip_quota is not None

    @property
    def quota_remaining(self) -> float:
        u_rem = self.user_quota.remaining
        v_rem = self.vip_quota.remaining if self.vip_quota else 0.0
        return u_rem + v_rem

    def __rich_repr__(self):
        """对敏感字段进行脱敏"""
        yield "username", self.username
        
        masked_cookies = {}
        if self.cookies:
            for k, v in self.cookies.items():
                if len(v) > 8:
                    masked_v = f"{v[:2]}******{v[-4:]}"
                else:
                    masked_v = "******"
                masked_cookies[k] = masked_v
        
        yield "cookies", masked_cookies

        yield "user_quota", self.user_quota
        yield "level", self.level
        yield "nickname", self.nickname
        yield "vip_quota", self.vip_quota
        yield "order", self.order
        yield "status", self.status
        
        if self.note:
            yield "note", self.note