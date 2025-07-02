from typing import Optional

from core import Picker, PICKERS, VolInfo

@PICKERS.register()
class ArgsFilterPicker(Picker):
    """
    通过命令行参数过滤卷信息的选择器。
    """

    def __init__(self, volume: str, max_size: Optional[float] = None, limit: Optional[int] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._volume = volume
        self._max_size: Optional[float] = max_size
        self._limit: Optional[int] = limit

    def pick(self, volumes: list[VolInfo]) -> list[VolInfo]:
        volume_data = volumes

        if not self._volume == 'all':
            volumes_choice = self._volume.split(',')
            volumes_choice = [v.strip() for v in volumes_choice]
            volume_data = filter(lambda x: any([v in x.name for v in volumes_choice]), volume_data)

        volume_data = filter(lambda x: self._max_size is None or x.size <= self._max_size, volume_data)

        if self._limit is not None:
            return list(volume_data)[:self._limit]
        else:
            return list(volume_data)
