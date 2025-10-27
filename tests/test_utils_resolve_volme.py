import unittest

from kmdr.module.picker.utils import resolve_volume
from kmdr.core.error import ArgsResolveError
class TestVolumeResolve(unittest.TestCase):

    def test_resolve_volume_all(self):
        ret = resolve_volume("all")

        assert ret is None

    def test_resolve_volume_simple_digit(self):

        ret = resolve_volume("1,2,3")

        assert isinstance(ret, set)
        assert ret == {1, 2, 3}

        ret = resolve_volume("4")

        assert isinstance(ret, set)
        assert ret == {4}

        ret = resolve_volume("1-3")

        assert isinstance(ret, set)
        assert ret == {1, 2, 3}

    def test_resolve_volume_range(self):

        ret = resolve_volume("1,3,4-6")

        assert isinstance(ret, set)
        assert ret == {1, 3, 4, 5, 6}

        ret = resolve_volume("1-3,4-6")

        assert isinstance(ret, set)
        assert ret == {1, 2, 3, 4, 5, 6}

        ret = resolve_volume("1-4,3-6")

        assert isinstance(ret, set)
        assert ret == {1, 2, 3, 4, 5, 6}

    def test_resolve_volume_invalid(self):

        with self.assertRaises(ArgsResolveError):
            resolve_volume("invalid")

        with self.assertRaises(ArgsResolveError):
            resolve_volume("-1,2")

        

