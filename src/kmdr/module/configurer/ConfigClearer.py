from kmdr.core import Configurer, CONFIGURER

@CONFIGURER.register()
class ConfigClearer(Configurer):
    def __init__(self, clear: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._clear = clear

    def operate(self) -> None:
        try:
            self._configurer.clear(self._clear)
        except KeyError as e:
            self._console.print(e.args[0])
            exit(1)

        self._console.print(f"Cleared configuration: {self._clear}")