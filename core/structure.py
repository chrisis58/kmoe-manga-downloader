from dataclasses import dataclass
from enum import Enum
from typing import Optional

class VolumeType(Enum):
    VOLUME = "單行本"
    EXTRA = "番外篇"
    SERIALIZED = "連載話"

@dataclass
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


@dataclass
class BookInfo:
    id: str
    name: str
    url: str
    author: str
    status: str
    last_update: str


@dataclass
class Config:

    retry_times: Optional[int] = None
    dest: Optional[str] = None
    callback: Optional[str] = None

    cookie: Optional[dict[str, str]] = None
    
