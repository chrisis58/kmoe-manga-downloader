import os

import unittest
from argparse import Namespace

from kmdr.core.defaults import Configurer
from kmdr.main import main_sync as kmdr_main

BASE_DIR = os.environ.get('KMDR_TEST_DIR', './tests')

configurer = Configurer()

class TestKmdrConfigOption(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        configurer.clear('option')

    @classmethod
    def tearDownClass(cls):
        configurer.clear('option')

    def tearDown(self):
        configurer.clear('option')

    def test_invalid_options(self):
        kmdr_main(
            Namespace(
                command='config',
                set=[
                    'other_invalid_arg=other',
                    'dest=some:path:that:does:not:exist',
                    'num_workers=not_a_number',
                    'retry=not_a_number',
                ]
            )
        )

        self.assertIsNone(configurer.option,
            "No options should be set due to invalid values")
            

    def test_set_options(self):
        os.makedirs(
            os.path.join(BASE_DIR, self.test_set_options.__name__),
            exist_ok=True
        )

        kmdr_main(
            Namespace(
                command='config',
                set=[
                    f'dest={os.path.join(BASE_DIR, self.test_set_options.__name__)}',
                    'num_workers=4',
                    'retry=5',
                    'callback=echo \'{v.name}\' downloaded!'
                ]
            )
        )

        self.assertEqual(configurer.option['dest'], os.path.join(BASE_DIR, self.test_set_options.__name__))
        self.assertEqual(configurer.option['num_workers'], 4)
        self.assertEqual(configurer.option['retry'], 5)
        self.assertEqual(configurer.option['callback'], "echo '{v.name}' downloaded!")

        os.rmdir(os.path.join(BASE_DIR, self.test_set_options.__name__))