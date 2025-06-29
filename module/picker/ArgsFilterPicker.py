from core import Picker, PICKERS, VolInfo

@PICKERS.register()
class ArgsFilterPicker(Picker):
    """
    通过命令行参数过滤卷信息的选择器。
    """

    def __init__(self, volume: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._volume = volume

    def pick(self, volumes: list[VolInfo]) -> list[VolInfo]:
        if self._volume == 'all':
            return volumes
        else:
            volumes_choice = self._volume.split(',')

            volume_data = filter(lambda x: sum([v in x.name for v in volumes_choice]) > 0, volumes)

            return list(volume_data)
