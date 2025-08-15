from typing import Optional, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from argparse import Namespace

from .defaults import combine_args

T = TypeVar('T')

class Registry(Generic[T]):

    def __init__(self, name: str, combine_args: bool = False):
        self._name = name
        self._modules: list['Predication'] = list()
        self._combine_args = combine_args

    def register(self,
            hasattrs: frozenset[str] = frozenset(),
            containattrs: frozenset[str] = frozenset(),
            hasvalues: dict[str, object] = dict(),
            predicate: Optional[Callable[[Namespace], bool]] = None,
            order: int = 0,
            name: Optional[str] = None
    ):
        """
        注册一个模块到注册表中。
        总体的匹配逻辑: `{predicate} or {hasvalues} and ({hasattrs} or {containattrs})`

        :param hasattrs: 模块处理的参数集合，必须全部匹配。如果未提供，则从类的 __init__ 方法中获取不可缺省的参数
        :param containattrs: 模块处理的可选参数集合，只要满足其中一个即可。
        :param hasvalues: 模块处理的属性值集合，必须全部满足。
        :param predicate: 可以提供预定义以外的条件，只要满足该条件就视为匹配。
        :param order: 模块的优先级，数字越小优先级越高。
        :param name: 模块的名称，如果未提供，则使用类名。
        """

        def wrapper(cls):
            nonlocal hasattrs
            nonlocal containattrs
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
                containattrs=frozenset(containattrs),
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
        if self._combine_args:
            condition = combine_args(condition)
        return self._get(condition)
    
    def _get(self, condition: Namespace) -> T:
        if not self._modules or len(self._modules) == 0:
            raise ValueError(f'{self._name} has no registered modules')

        if len(self._modules) == 1:
            return self._modules[0].cls(**self._filter_nonone_args(condition))
        
        for module in self._modules:
            if (module.predicate is not None and module.predicate(condition)) or \
                    all(hasattr(condition, attr) and getattr(condition, attr) == value for attr, value in module.hasvalues.items()) and \
                    (all(hasattr(condition, attr) and getattr(condition, attr) is not None for attr in module.hasattrs) \
                            or any(hasattr(condition, attr) for attr in module.containattrs)):

                # 手动配置的 predicate 优先级最高，只要满足 predicate 条件就返回
                # hasvalues 配置的属性值必须完全匹配
                # hasattrs 和 containattrs 二者只需要满足一个
                
                return module.cls(**self._filter_nonone_args(condition))

        raise ValueError(f'{self._name} does not have a module for {condition}')
    
    def _filter_nonone_args(self, condition: Namespace) -> dict[str, object]:
        return {k: v for k, v in vars(condition).items() if v is not None}

@dataclass(frozen=True)
class Predication:
    cls: type

    hasattrs: frozenset[str] = frozenset({})
    containattrs: frozenset[str] = frozenset({})
    hasvalues: dict[str, object] = field(default_factory=dict)
    predicate: Optional[Callable[[Namespace], bool]] = None

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
