from typing import Optional

from kmdr.core import PICKERS, Picker, VolInfo, VolumeType
from kmdr.core.error import ArgsResolveError

from .utils import resolve_volume


@PICKERS.register(
    predicate=lambda args: (
        getattr(args, "volume", None) is not None
        or getattr(args, "vol_ids", None) is not None
    ),
)
class ArgsFilterPicker(Picker):
    """
    通过命令行参数过滤卷信息的选择器。

    支持按卷索引（-v/--volume）和卷 ID（--vol-ids）两种筛选方式。
    两种方式均为可选，但至少需要提供一个；同时提供时取交集。
    """

    def __init__(
        self,
        volume: Optional[str] = None,
        vol_type: str = "vol",
        max_size: Optional[float] = None,
        limit: Optional[int] = None,
        vol_ids: Optional[str] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._volume = volume
        self._vol_ids: Optional[set[str]] = set(vol_ids.split(",")) if vol_ids else None
        self._vol_type = self.__get_volume_type(vol_type)
        self._max_size: Optional[float] = max_size
        self._limit: Optional[int] = limit

    def pick(self, volumes: list[VolInfo]) -> list[VolInfo]:
        if self._volume is None and self._vol_ids is None:
            raise ArgsResolveError("未指定卷筛选条件：请提供 --volume (-v) 或 --vol-ids 中的至少一个")

        volume_data = volumes

        if self._vol_type is not None:
            volume_data = filter(lambda x: x.vol_type == self._vol_type, volume_data)

        if self._volume is not None and (choice := resolve_volume(self._volume)) is not None:
            volume_data = filter(lambda x: x.index in choice, volume_data)

        if self._vol_ids is not None:
            volume_data = filter(lambda x: x.id in self._vol_ids, volume_data)

        if self._max_size is not None:
            volume_data = filter(
                lambda x: self._max_size is None or x.size <= self._max_size,
                volume_data,
            )

        if self._limit is not None:
            return list(volume_data)[: self._limit]
        else:
            return list(volume_data)

    def __get_volume_type(self, vol_type: str) -> Optional[VolumeType]:
        assert vol_type in {"vol", "extra", "seri", "all"}, f"Invalid volume type: {vol_type}"

        if vol_type == "vol":
            return VolumeType.VOLUME
        elif vol_type == "extra":
            return VolumeType.EXTRA
        elif vol_type == "seri":
            return VolumeType.SERIALIZED
        elif vol_type == "all":
            return None
        else:
            raise ValueError(f"Unknown volume type: {vol_type}")
