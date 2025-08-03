from core import CONFIGURER, Configurer

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
            print("No configurations found.")
            return

        print("Current configurations:")
        for key, value in self._configurer.option.items():
            print(f"\t{key} = {value}")