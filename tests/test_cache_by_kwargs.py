import unittest

from kmdr.module.downloader.utils import cached_by_kwargs, clear_cache

@cached_by_kwargs
def add(a, b, c):
    return a + b + c

class TestAdder(object):

    @cached_by_kwargs
    def add(self, a, b, c):
        return a + b + c
    
class AddUtil:

    @staticmethod
    @cached_by_kwargs
    def add(a, b, c):
        return a + b + c

    @classmethod
    @cached_by_kwargs
    def mul(cls, a, b, c):
        return a * b * c

class TestCacheByKwargs(unittest.TestCase):

    def tearDown(self):
        clear_cache(add)
        clear_cache(TestAdder.add)
        clear_cache(AddUtil.add)
        clear_cache(AddUtil.mul)

    def test_function_cache(self):
        result1 = add(1, 2, c=3)
        result2 = add(3, 2, c=3)
        self.assertEqual(result1, result2)

    def test_classmethod_cache(self):
        result1 = AddUtil.add(1, 2, c=6)
        result2 = AddUtil.add(3, 2, c=6)
        self.assertEqual(result1, result2)

    def test_instance_method_cache(self):
        instance = TestAdder()
        result1 = instance.add(1, 2, c=9)
        result2 = instance.add(3, 2, c=9)
        self.assertEqual(result1, result2)

    def test_different_definitions(self):
        result1 = add(1, b=2, c=3)
        result2 = AddUtil.add(2, b=2, c=3)
        result3 = TestAdder().add(3, b=2, c=3)

        self.assertNotEqual(result1, result2)
        self.assertNotEqual(result1, result3)
        self.assertNotEqual(result2, result3)

    def test_classmethod_cache(self):
        result1 = AddUtil.mul(1, 2, c=3)
        result2 = AddUtil.mul(2, 2, c=3)
        self.assertEqual(result1, result2)

    def test_different_instance(self):
        instance1 = TestAdder()
        instance2 = TestAdder()
        result1 = instance1.add(1, 2, c=12)
        result2 = instance2.add(2, 3, c=12)

        self.assertEqual(result1, result2)

    def test_clear_cache(self):
        result1 = add(1, 2, c=0)
        clear_cache(add)
        result2 = add(2, 3, c=0)
        self.assertNotEqual(result1, result2)

        result1 = AddUtil.add(1, 2, c=0)
        clear_cache(AddUtil.add)
        result2 = AddUtil.add(2, 3, c=0)
        self.assertNotEqual(result1, result2)

        result1 = TestAdder().add(1, 2, c=0)
        clear_cache(TestAdder.add)
        result2 = TestAdder().add(2, 3, c=0)
        self.assertNotEqual(result1, result2)
