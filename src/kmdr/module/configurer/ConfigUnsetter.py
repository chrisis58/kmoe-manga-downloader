from kmdr.core import Configurer, CONFIGURER

@CONFIGURER.register()
class ConfigUnsetter(Configurer):
    def __init__(self, unset: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._unset = unset

    def operate(self) -> None:
        if not self._unset:
            print("No option specified to unset.")
            return
        
        self._configurer.unset_option(self._unset)
        print(f"Unset configuration: {self._unset}")