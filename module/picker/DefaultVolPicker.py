from core import Picker, PICKERS, VolInfo

@PICKERS.register()
class DefaultVolPicker(Picker):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def pick(self, volumes: list[VolInfo]) -> list[VolInfo]:
        print("\t卷类型\t卷名\t页数\t大小(MB)")
        for v in range(len(volumes)):
            print(f"[{v}]\t{volumes[v].vol_type.value}\t{volumes[v].name}\t{volumes[v].pages}\t{volumes[v].size:.2f}")

        choosed = input("choose a volume to download (use comma to select multiple volumes or just 'all'):\n")

        if choosed.strip() == '':
            return []
        elif choosed.strip().lower() == 'all':
            return volumes

        choosed = choosed.split(',')
        choosed = [x.strip() for x in choosed]
        choosed = [int(x) for x in choosed if x.isdigit() and 0 <= int(x) < len(volumes)]

        return [volumes[i] for i in choosed] if choosed else []