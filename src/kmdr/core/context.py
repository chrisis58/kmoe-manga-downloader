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

    @property
    def _session(self) -> ClientSession:
        return session_var.get()

    @property
    def _base_url(self) -> str:
        return base_url_var.get()

    @_base_url.setter
    def _base_url(self, value: str):
        base_url_var.set(value)
