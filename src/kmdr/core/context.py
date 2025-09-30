from aiohttp import ClientSession


from .constants import BASE_URL
from .defaults import Configurer as InnerConfigurer, UserProfile, session_var, progress, console

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
        self._base_url: str = BASE_URL.DEFAULT
        self._session: ClientSession = session_var.get()
