from typing import Protocol, TypeVar

S = TypeVar('S', covariant=True)
T = TypeVar('T', contravariant=True)

class Supplier(Protocol[S]):
    def __call__(self) -> S: ...

class Consumer(Protocol[T]):
    def __call__(self, value: T) -> None: ...
