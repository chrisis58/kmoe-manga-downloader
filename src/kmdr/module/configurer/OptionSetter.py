from kmdr.core import Configurer, CONFIGURER

from .option_validate import validate

@CONFIGURER.register()
class OptionSetter(Configurer):
    def __init__(self, set: list[str], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._set = set

    def operate(self) -> None:
        for option in self._set:
            if '=' not in option:
                print(f"Invalid option format: `{option}`. Expected format is key=value.")
                continue

            key, value = option.split('=', 1)
            key = key.strip()
            value = value.strip()

            validated_value = validate(key, value)
            if validated_value is None:
                continue

            self._configurer.set_option(key, validated_value)
            print(f"Set configuration: {key} = {validated_value}")






