import os
import json

from core import Authenticator

class CookieAuthenticator(Authenticator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        with open(os.path.join(os.path.expanduser("~"), '.koxdl'), 'r') as f:
            self._cookies = json.load(f)

    def authenticate(self) -> bool:
        if not self._cookies:
            return False
        
        self._session.cookies.update(self._cookies)
        return True