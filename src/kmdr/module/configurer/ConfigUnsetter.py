from kmdr.core import Configurer, CONFIGURER

from .option_validate import check_key

@CONFIGURER.register()
class ConfigUnsetter(Configurer):
    def __init__(self, unset: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._unset = unset

    def operate(self) -> None:
        if not self._unset:
            self._console.print("[yellow]请提供要取消设置的配置项。[/yellow]")
            return

        check_key(self._unset)
        self._configurer.unset_option(self._unset)
        self._console.print(f"[green]取消配置项: {self._unset}[/green]")