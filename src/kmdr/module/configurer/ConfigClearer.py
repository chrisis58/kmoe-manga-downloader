from kmdr.core import Configurer, CONFIGURER

@CONFIGURER.register()
class ConfigClearer(Configurer):
    def __init__(self, clear: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._clear = clear

    def operate(self) -> None:
        self._configurer.clear(self._clear)
        print(f"Cleared configuration: {self._clear}")