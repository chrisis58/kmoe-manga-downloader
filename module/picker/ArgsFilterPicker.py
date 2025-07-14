from typing import Optional

from core import Picker, PICKERS, VolInfo, VolumeType

@PICKERS.register()
class ArgsFilterPicker(Picker):
    """
    通过命令行参数过滤卷信息的选择器。
    """

    def __init__(self, volume: str, vol_type: str = 'vol', max_size: Optional[float] = None, limit: Optional[int] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._volume = volume
        self._vol_type = self.__get_volume_type(vol_type)
        self._max_size: Optional[float] = max_size
        self._limit: Optional[int] = limit

    def pick(self, volumes: list[VolInfo]) -> list[VolInfo]:
        volume_data = volumes

        if self._vol_type is not None:
            volume_data = filter(lambda x: x.vol_type == self._vol_type, volume_data)

        if (choice := self.__resolve_volume(self._volume)) is not None:
            volume_data = filter(lambda x: x.index in choice, volume_data)

        if self._max_size is not None:
            volume_data = filter(lambda x: x.size <= self._max_size, volume_data)

        if self._limit is not None:
            return list(volume_data)[:self._limit]
        else:
            return list(volume_data)
        
    def __get_volume_type(self, vol_type: str) -> Optional[VolumeType]:
        assert vol_type in {'vol', 'extra', 'seri', 'all'}, f"Invalid volume type: {vol_type}"

        if vol_type == 'vol':
            return VolumeType.VOLUME
        elif vol_type == 'extra':
            return VolumeType.EXTRA
        elif vol_type == 'seri':
            return VolumeType.SERIALIZED
        elif vol_type == 'all':
            return None
        else:
            raise ValueError(f"Unknown volume type: {vol_type}")
        
    def __resolve_volume(self, volume: str) -> Optional[list[int]]:
        if volume == 'all':
            return None
        
        if '-' in volume and volume.count('-') == 1 and ',' not in volume:
            start, end = volume.split('-')
            start = int(start.strip())
            end = int(end.strip())
            return list(range(start, end + 1))
        
        volumes_choice = volume.split(',')
        volumes_choice = [v.strip() for v in volumes_choice]
        volumes_choice = [int(v) for v in volumes_choice if v.isdigit() and int(v) > 0]

        return volumes_choice
