from os import environ

import unittest
from argparse import Namespace

from core import *
from module import *

from kmdr import main as kmdr_main

BASE_DIR = environ.get('KMDR_TEST_DIR', './tests')

class TestKmdr(unittest.TestCase):

    @classmethod
    def tearDownClass(cls):
        from shutil import rmtree
        from os import path

        test_methods = [method for method in dir(cls) if method.startswith('test_')]

        for method in test_methods:
            dir_path = f"{BASE_DIR}/{method}"
            
            if path.exists(dir_path):
                rmtree(dir_path)

    def test_download_multiple_volumes(self):
        kmdr_main(
            Namespace(
                command='download',
                dest=f'{BASE_DIR}/{self.test_download_multiple_volumes.__name__}',
                book_url='https://kox.moe/c/51043.htm',
                book_name=None,
                volume='all',
                max_size=0.5,
                limit=3,
                retry=3,
            )
        )

    def test_download_volume_with_callback(self):
        kmdr_main(
            Namespace(
                command='download',
                dest=f'{BASE_DIR}/{self.test_download_volume_with_callback.__name__}',
                book_url='https://kox.moe/c/51043.htm',
                book_name=None,
                volume='all',
                max_size=0.4,
                limit=1,
                retry=3,
                callback="echo 'CALLBACK: {b.name} {v.name} has been downloaded!'"
            )
        )
