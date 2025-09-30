from rich.table import Table
from rich.pretty import Pretty

from kmdr.core import CONFIGURER, Configurer

@CONFIGURER.register(
    hasvalues={
        'list_option': True
    }
)
class OptionLister(Configurer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def operate(self) -> None:
        if self._configurer.option is None and self._configurer.base_url is None:
            self._console.print("[blue]当前没有任何配置项。[/blue]")
            return

        table = Table(title="[green]当前 Kmdr 配置项[/green]", show_header=False, header_style="blue")

        table.add_column("配置类型 (Type)", style="magenta", no_wrap=True, min_width=10)
        table.add_column("配置项 (Key)", style="cyan", no_wrap=True, min_width=10)
        table.add_column("值 (Value)", no_wrap=False, min_width=20)

        if self._configurer.option is not None:
            for idx, (key, value) in enumerate(self._configurer.option.items()):
                value_to_display = value
                if isinstance(value, (dict, list, set, tuple)):
                    value_to_display = Pretty(value)

                table.add_row('下载配置' if idx == 0 else '', key, value_to_display)
                table.add_section()

        if self._configurer.base_url is not None:
            table.add_row('应用配置', '镜像地址', self._configurer.base_url or '未设置')

        self._console.print(table)