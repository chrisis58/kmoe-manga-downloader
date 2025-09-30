from dataclasses import dataclass
from enum import Enum
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
