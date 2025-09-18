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
        if self._configurer.option is None:
            self._console.print("[blue]当前没有任何配置项。[/blue]")
            return

        table = Table(title="[green]当前 Kmdr 配置项[/green]", show_header=False, header_style="blue")

        table.add_column("配置项 (Key)", style="cyan", no_wrap=True, min_width=10)
        table.add_column("值 (Value)", style="white", no_wrap=False, min_width=20)

        for key, value in self._configurer.option.items():
            value_to_display = value
            if isinstance(value, (dict, list, set, tuple)):
                value_to_display = Pretty(value)
            
            table.add_row(key, value_to_display)
            table.add_section()
        
        self._console.print(table)