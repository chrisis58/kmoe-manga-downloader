from kmdr.core import Configurer, CONFIGURER

@CONFIGURER.register()
class BaseUrlUpdator(Configurer):
    def __init__(self, base_url: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._base_url = base_url

    def operate(self) -> None:
        try:
            self._configurer.set_base_url(self._base_url)
        except KeyError as e:
            self._console.print(e.args[0])
            exit(1)

        self._console.print(f"已设置基础 URL: {self._base_url}")