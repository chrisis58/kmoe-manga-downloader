import dataclasses
import json
from enum import Enum


class KmdrJSONEncoder(json.JSONEncoder):
    """用于写入本地配置文件的基础编码器（包含敏感数据）"""

    def default(self, o):
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)

        if isinstance(o, Enum):
            return o.value

        return super().default(o)


class SafeJSONEncoder(KmdrJSONEncoder):
    """用于工具调用的安全编码器，会自动脱敏标记为 sensitive=True 的字段"""

    def default(self, o):
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            result = {}
            for f in dataclasses.fields(o):
                val = getattr(o, f.name)
                if f.metadata.get("sensitive"):
                    result[f.name] = "***SENSITIVE***"
                else:
                    result[f.name] = val
            return result
        return super().default(o)
