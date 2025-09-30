from aiohttp import ClientSession


from .defaults import Configurer as InnerConfigurer, UserProfile, session_var, progress, console, base_url_var

class TerminalContext:

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._progress = progress
        self._console = console

class UserProfileContext:

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._profile = UserProfile()

class ConfigContext:

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._configurer = InnerConfigurer()

class SessionContext:

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._base_url: str = base_url_var.get()
        self._session: ClientSession = session_var.get()

    def _set_base_url(self, value: str):
        self._base_url = value
        base_url_var.set(value)
