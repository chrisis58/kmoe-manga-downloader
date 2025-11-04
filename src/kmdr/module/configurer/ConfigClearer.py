from kmdr.core import Configurer, CONFIGURER
from kmdr.core.console import info

@CONFIGURER.register()
class ConfigClearer(Configurer):
    def __init__(self, clear: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._clear = clear

    def operate(self) -> None:
        try:
            self._configurer.clear(self._clear)
        except KeyError as e:
            info(f"[red]{e.args[0]}[/red]")
            return

        info(f"[green]已清除: {self._clear}[/green]")