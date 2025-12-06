from dataclasses import dataclass, field, replace
from typing import Any, Literal, Optional, Union, overload

from utils import isanyofinstance


class VarEnv:
    def __init__(self):
        self.types = {}
        self.dims = {}

    def clear(self):
        self.types.clear()
        self.dims.clear()

    def __getitem__(self, key):
        return self.__getattribute__(key)


varenv = VarEnv()


T = Union[
    "NoneType",
    "VarType",
    "NeverType",
    "AnyType",
    "RangeType",
    "NumberType",
    "BoolType",
    "StrType",
    "SliceType",
    "ListType",
    "FunctionType",
]


@dataclass(kw_only=True, frozen=True)
class UType:
    _meta: dict = field(default_factory=dict)
    node: Optional[int] = None
    dim: Optional[list] = None

    @overload
    def name(self) -> str: ...
    @overload
    def name(self, *names: str) -> str: ...
    def name(self, *names: Optional[str]) -> str | bool:
        n = self.__class__.__name__.removesuffix("Type")
        if names:
            return n in names
        return n

    def type(self) -> str:
        return self.name()

    def edit(self, **kwargs):
        if "_meta" not in kwargs:
            kwargs["_meta"] = dict(self._meta)
        return replace(self, **kwargs)

    def complete(self, value: Optional[T] = None):
        """Complete anonymous types ?T"""
        return self

    def meta(self, key, value=None):
        if value is not None:
            self._meta[key] = value
        return self._meta.get(key)


class NoneType(UType):
    pass


@dataclass(kw_only=True, frozen=True)
class NumberType(UType):
    typ: Literal["Int", "Float"] = "Float"
    dim: Optional[list] = None
    value: float | int = 0

    def type(self) -> str:
        from .utils import format_dimension

        d = f"[[bold]{format_dimension(self.dim)}[/bold]]" if self.dim != [] else "[1]"
        return self.typ + d

    @overload
    def name(self) -> str: ...
    @overload
    def name(self, *names: str) -> str: ...
    def name(self, *names: Optional[str]) -> str | bool:
        n = self.typ
        if names:
            return n in names
        return n


@dataclass(kw_only=True, frozen=True)
class BoolType(UType):
    pass


@dataclass(kw_only=True, frozen=True)
class StrType(UType):
    pass


@dataclass(frozen=True)
class VarType(UType):
    _name: str
    kind: str = "types"

    def type(self) -> str:
        if self._name not in varenv[self.kind]:
            return "?" + self._name
        return varenv[self.kind][self._name].type()

    def complete(self, value: Optional[T] = None):
        if value is None:
            return varenv[self.kind].get(self._name, self)
        if self._name not in varenv[self.kind]:
            varenv[self.kind][self._name] = value
        elif not unify(value, varenv[self.kind][self._name]) or not dimcheck(
            value, varenv[self.kind][self._name]
        ):
            return self
        return value


@dataclass(frozen=True)
class VarDim(VarType):
    _name: str
    kind: str = "dims"


@dataclass(kw_only=True, frozen=True)
class NeverType(UType):
    def __eq__(self, other) -> bool:
        return True


@dataclass(kw_only=True, frozen=True)
class UndefinedType(UType):
    pass


@dataclass(kw_only=True, frozen=True)
class ListType(UType):
    content: T = NeverType()
    dim: Optional[list] = content.dim

    def __post_init__(self):
        if self.dim is None:
            object.__setattr__(self, "dim", self.content.dim)

    def type(self) -> str:
        return f"List[{self.content.type()}]"

    def complete(self, value: Optional[T] = None):
        return self.edit(content=self.content.complete(getattr(value, "content", None)))


@dataclass(kw_only=True, frozen=True)
class SliceType(UType):
    pass


@dataclass(kw_only=True, frozen=True)
class RangeType(UType):
    value: NumberType = NumberType(typ="Int")


@dataclass(kw_only=True, frozen=True)
class FunctionType(UType):
    params: list[T] = field(default_factory=list)
    return_type: T = field(default_factory=lambda: AnyType())
    param_names: list[str] = field(default_factory=list)
    param_addrs: list[str] = field(default_factory=list)
    param_defaults: list[T] = field(default_factory=list)
    arity: tuple[int, int] = (0, 0)
    unresolved: Optional[Literal["recursive", "parameters"]] = None
    _name: Optional[str] = field(default=None, compare=False)
    _loc: Any = field(default=None)

    def type(self):
        args = [
            f"{name}: {param.type()}"
            for name, param in zip(self.param_names, self.params)
        ]
        if self.arity[0] != self.arity[1]:
            args.insert(self.arity[0], "/")

        return f"![\\[{', '.join(args)}], {self.return_type.type()}]"

    def check_args(self, *args: T) -> Optional["FunctionType"]:
        global varenv
        varenv.clear()
        params = [
            param.complete(arg) if not isinstance(param, AnyType) else NeverType()
            for param, arg in zip(self.params, args)
        ]
        if len(args) == len(self.params) and all(
            unify(p, a) and dimcheck(p, a) for p, a in zip(params, args)
        ):
            return self.edit(return_type=self.return_type.complete())


class AnyType(UType):
    unresolved: Optional[str] = None

    def __new__(cls, name: str = "any", unresolved=None, **kwargs) -> "T":
        if name.lower() == "any":
            return super().__new__(cls)

        t = {
            "none": NoneType(),
            "number": NumberType(),
            "int": NumberType(typ="Int"),
            "float": NumberType(typ="Float"),
            "bool": BoolType(),
            "str": StrType(),
            "list": ListType(),
            "slice": SliceType(),
            "range": RangeType(),
            "function": FunctionType(),
        }.get(name.strip().lower())

        if t is None:
            raise ValueError(f"Unknown type name: {name!r}")

        t = t.edit(**kwargs)
        return t

    def __init__(self, name="any", unresolved=None, **kwargs):
        self.unresolved = unresolved
        super().__init__()


def unify(a: T, b: T) -> Optional[T]:
    if isanyofinstance((a, b), AnyType):
        return None
    match a, b:
        case NeverType(), _:
            return b
        case _, NeverType():
            return a
        case AnyType(), _:
            return None
        case _, AnyType():
            return None
        case NumberType(), NumberType():
            return (
                a
                if a.typ == b.typ
                or a.meta("#dimension-only")
                or b.meta("#dimension-only")
                else None
            )
        case ListType(), ListType():
            content = unify(a.content, b.content)
            return (
                ListType(content=content, _meta=a._meta | b._meta) if content else None
            )
        case FunctionType(), FunctionType():
            if a.arity != b.arity:
                return
            parts = [
                (unify(x, y) if "Any" not in (x.name(), y.name()) else AnyType())
                and dimcheck(x, y)
                for x, y in zip(a.params + [a.return_type], b.params + [b.return_type])
            ]
            return a if all(parts) else None
        case _, _:
            return a if a.type() == b.type() else None


def dimcheck(a: T, b: T) -> bool:
    if a.name("Never", "Any") or b.name("Never", "Any"):
        return True

    dims = [a.dim, b.dim]
    if any(item is None for item in dims):
        return True

    return dims[0] == dims[1]


@dataclass(frozen=True)
class Dimension:
    dimension: list = field(default_factory=list)


class Overload:
    functions: list[FunctionType] = []

    def __init__(self, *functions: "FunctionType|Overload"):
        for func in functions:
            self.functions.extend(
                [func] if isinstance(func, FunctionType) else func.functions
            )


@dataclass(frozen=True)
class Struct:
    fields: dict[str, T | Overload]

    def __getitem__(self, key: str) -> T | Overload | None:
        return self.fields.get(key)


class IntType:
    def __new__(cls) -> NumberType:
        return NumberType(typ="Int")


class FloatType:
    def __new__(cls) -> NumberType:
        return NumberType(typ="Float")
