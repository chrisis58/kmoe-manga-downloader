from rich.table import Table
from rich.prompt import Prompt

from kmdr.core import Picker, PICKERS, VolInfo

from .utils import resolve_volume

@PICKERS.register()
class DefaultVolPicker(Picker):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def pick(self, volumes: list[VolInfo]) -> list[VolInfo]:
        table = Table(title="可用卷列表", show_header=True, header_style="bold blue")
        table.add_column("序号", style="dim", width=4, justify="center")
        table.add_column("卷名", style="cyan", no_wrap=True, min_width=20)
        table.add_column("索引", style="blue", justify="center")
        table.add_column("卷类型", style="green", justify="center")
        table.add_column("页数", style="blue", justify="right")
        table.add_column("大小(MB)", style="yellow", justify="right")

        last_vol_type = None
        for index, volume in enumerate(volumes):
            if last_vol_type is not None and volume.vol_type != last_vol_type:
                table.add_section()
            last_vol_type = volume.vol_type

            table.add_row(
                str(index + 1),
                volume.name,
                str(volume.index),
                volume.vol_type.value,
                str(volume.pages),
                f"{volume.size:.2f}"
            )
        
        self._console.print(table)
        
        choice_str = Prompt.ask(
            "[green]请选择要下载的卷序号 (例如 'all', '1,2,3', '1-3,4-6')[/green]",
            default="all"
        )

        chosen_indices = resolve_volume(choice_str)

        if not chosen_indices:
            return volumes

        return [volumes[i - 1] for i in chosen_indices if 1 <= i <= len(volumes)]