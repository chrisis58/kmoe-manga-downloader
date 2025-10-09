from typing import Protocol, TypeVar

T = TypeVar('T')

class Suppiler(Protocol[T]):
    def __call__(self) -> T: ...

class Consumer(Protocol[T]):
    def __call__(self, value: T) -> None: ...
