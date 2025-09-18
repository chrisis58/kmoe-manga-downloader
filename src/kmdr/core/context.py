from aiohttp import ClientSession

from .defaults import Configurer as InnerConfigurer, UserProfile, session_var, progress, console

class TerminalContext:

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._progress = progress
        self._console = console

class SessionContext:

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._session: ClientSession = session_var.get()

class UserProfileContext:

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._profile = UserProfile()

class ConfigContext:

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._configurer = InnerConfigurer()
