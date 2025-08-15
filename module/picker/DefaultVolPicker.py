from core import Picker, PICKERS, VolInfo

from .utils import resolve_volume

@PICKERS.register()
class DefaultVolPicker(Picker):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def pick(self, volumes: list[VolInfo]) -> list[VolInfo]:
        print("\t卷类型\t页数\t大小(MB)\t卷名")
        for index, volume in enumerate(volumes):
            print(f"[{index + 1}]\t{volume.vol_type.value}\t{volume.pages}\t{volume.size:.2f}\t\t{volume.name}")

        choosed = input("choose a volume to download (e.g. 'all', '1,2,3', '1-3,4-6'):\n")

        if (chosen := resolve_volume(choosed)) is None:
            return volumes

        return [volumes[i - 1] for i in chosen]