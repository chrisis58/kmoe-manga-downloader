from kmdr.core import Configurer, CONFIGURER
from kmdr.core.console import info

from .option_validate import validate

@CONFIGURER.register()
class OptionSetter(Configurer):
    def __init__(self, set: list[str], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._set = set

    def operate(self) -> None:
        for option in self._set:
            if '=' not in option:
                info(f"[red]无效的选项格式: `{option}`。[/red] 应为 key=value 格式。")
                continue

            key, value = option.split('=', 1)
            key = key.strip()
            value = value.strip()

            validated_value = validate(key, value)
            if validated_value is None:
                continue

            self._configurer.set_option(key, validated_value)
            info(f"[green]已设置配置: {key} = {validated_value}[/green]")






