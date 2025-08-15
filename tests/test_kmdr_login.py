import os

import unittest
from argparse import Namespace

from kmdr.core.utils import clear_session_context
from kmdr.main import main as kmdr_main

KMOE_USERNAME = os.environ.get('KMOE_USERNAME')
KMOE_PASSWORD = os.environ.get('KMOE_PASSWORD')

@unittest.skipUnless(KMOE_USERNAME and KMOE_PASSWORD, "KMOE_USERNAME and KMOE_PASSWORD must be set in environment variables")
class TestKmdrLogin(unittest.TestCase):

    @classmethod
    def tearDownClass(cls):
        clear_session_context()

    def test_login_with_username_and_password(self):
        assert KMOE_USERNAME and KMOE_PASSWORD, "KMOE_USERNAME and KMOE_PASSWORD must be set in environment variables"

        kmdr_main(
            Namespace(
                command='login',
                username=KMOE_USERNAME,
                password=KMOE_PASSWORD,
                show_quota=False
            )
        )