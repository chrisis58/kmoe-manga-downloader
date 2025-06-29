from typing import Optional, Callable, TypeVar, Generic
from dataclasses import dataclass
from argparse import Namespace

T = TypeVar('T')

class Registry(Generic[T]):

    def __init__(self, name: str):
        self._name = name
        self._modules: list['Predication'] = list()

    def register(self,
            hasattrs: set[str] = frozenset(),
            hasvalues: dict[str, any] = dict(),
            predicate: Optional[Callable[[any], bool]] = None,
            order: int = 0,
            name: Optional[str] = None
    ):

        def wrapper(cls):
            nonlocal hasattrs
            nonlocal hasvalues
            nonlocal name
            nonlocal predicate

            if name is None:
                name = cls.__name__

            if not hasattrs or len(hasattrs) == 0:
                # 如果没有指定属性，则从类的 __init__ 方法中获取参数
                if hasattr(cls, '__init__'):
                    init_signature = cls.__init__.__code__.co_varnames[1:cls.__init__.__code__.co_argcount]
                    init_defaults = cls.__init__.__defaults__ or ()
                    default_count = len(init_defaults)
                    required_params = init_signature[:len(init_signature) - default_count]
                    hasattrs = frozenset(required_params)
                else:
                    raise ValueError(f'{self._name} requires at least one attribute to be specified for {name}')
            
            predication = Predication(
                cls=cls,
                hasattrs=frozenset(hasattrs),
                hasvalues=hasvalues,
                predicate=predicate,
                order=order
            )

            if predication in self._modules:
                raise ValueError(f'{self._name} already has a module for {predication}')
            
            self._modules.append(predication)
            self._modules.sort()

            return cls
        
        return wrapper
        
    def get(self, condition: Namespace) -> T:
        if len(self._modules) == 1:
            return self._modules[0].cls(**self._filter_nonone_args(condition))
        
        for module in self._modules:
            if all(hasattr(condition, attr) for attr in module.hasattrs) and \
               all(hasattr(condition, attr) and getattr(condition, attr) == value for attr, value in module.hasvalues.items()) and \
               (module.predicate is None or module.predicate(condition)):
                
                return module.cls(**self._filter_nonone_args(condition))

        raise ValueError(f'{self._name} does not have a module for {condition}')
    
    def _filter_nonone_args(self, condition: Namespace) -> dict[str, any]:
        return {k: v for k, v in vars(condition).items() if v is not None}

@dataclass(frozen=True)
class Predication:
    cls: type

    hasattrs: set[str] = frozenset({})
    hasvalues: dict[str, any] = frozenset({})
    predicate: Optional[Callable[[any], bool]] = None

    order: int = 0

    def __lt__(self, other: 'Predication') -> bool:
        if self.order == other.order:
            # 如果 order 相同，则比较 hasattrs 的长度
            # 通常情况下，hasattrs 的长度越长，优先级越高
            return len(self.hasattrs) > len(other.hasattrs)
        return self.order < other.order
    
    def __hash__(self) -> int:
        return hash((self.cls, self.hasattrs, frozenset(self.hasvalues.items()), self.predicate, self.order))
    
    def __eq__(self, other: 'Predication') -> bool:
        return (self.cls, self.hasattrs, frozenset(self.hasvalues.items()), self.predicate, self.order) == \
               (other.cls, other.hasattrs, frozenset(other.hasvalues.items()), other.predicate, other.order)
