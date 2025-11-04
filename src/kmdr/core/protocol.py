from typing import Protocol, TypeVar

S = TypeVar('S', covariant=True)
T = TypeVar('T', contravariant=True)

class Supplier(Protocol[S]):
    def __call__(self) -> S: ...

class Consumer(Protocol[T]):
    def __call__(self, value: T) -> None: ...

class AsyncCtxManager(Protocol[S]):
    async def __aenter__(self) -> S: ...
    async def __aexit__(self, exc_type, exc_value, traceback) -> None: ...