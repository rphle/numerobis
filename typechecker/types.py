from dataclasses import dataclass, field, replace
from typing import Any, Literal, Optional, Union, overload

from exceptions.exceptions import Mismatch
from nodes.unit import Expression, One
from utils import isallofinstance, isanyofinstance


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
    "DimensionType",
]


@dataclass(kw_only=True, frozen=True)
class UType:
    _meta: dict = field(default_factory=dict)
    node: Optional[int] = None
    dim: Optional[Expression | One] = None

    @overload
    def name(self) -> str: ...
    @overload
    def name(self, *names: str) -> str: ...
    def name(self, *names: Optional[str]) -> str | bool:
        n = self.__class__.__name__.removesuffix("Type")
        if names:
            return n in names
        return n

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

    def __str__(self):
        return f"'{self.name()}'"


class NoneType(UType):
    dim = One()

    def __eq__(self, other) -> bool:
        return isinstance(other, NoneType)


@dataclass(kw_only=True, frozen=True)
class NumberType(UType):
    typ: Literal["Int", "Float"] = "Float"
    dim: Optional[Expression | One] = None
    value: float | int = 0

    def __str__(self) -> str:
        d = str(self.dim) if self.dim else "[[bold]1[/bold]]"
        return f"'{self.typ}{d}'"

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
    def __eq__(self, other) -> bool:
        return isinstance(other, BoolType)


@dataclass(kw_only=True, frozen=True)
class StrType(UType):
    def __eq__(self, other) -> bool:
        return isinstance(other, StrType)


@dataclass(frozen=True)
class VarType(UType):
    _name: str
    kind: str = "types"

    def __str__(self) -> str:
        if self._name not in varenv[self.kind]:
            return "?" + self._name
        return str(varenv[self.kind][self._name])

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
    dim: Optional[Expression | One] = content.dim

    def __post_init__(self):
        if self.dim is None:
            object.__setattr__(self, "dim", self.content.dim)

    def __str__(self) -> str:
        return f"'List[{str(self.content).strip("'")}]'"

    def complete(self, value: Optional[T] = None):
        return self.edit(content=self.content.complete(getattr(value, "content", None)))


@dataclass(kw_only=True, frozen=True)
class SliceType(UType):
    def __eq__(self, other):
        return isinstance(other, SliceType)


@dataclass(kw_only=True, frozen=True)
class RangeType(UType):
    value: NumberType = NumberType(typ="Int")

    def __str__(self):
        return f"'Range[{self.value}]'"

    def __eq__(self, other):
        if not isinstance(other, RangeType):
            return False
        return self.value == other.value


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

    def __str__(self):
        args = [
            f"{name}: {str(param).strip("'")}"
            for name, param in zip(self.param_names, self.params)
        ]
        if self.arity[0] != self.arity[1]:
            args.insert(self.arity[0], "/")

        return f"![\\[{', '.join(args)}], {str(self.return_type).strip('')}]"

    def check_args(self, *args: T) -> "FunctionType | Mismatch | None":
        global varenv
        varenv.clear()
        params = [
            param.complete(arg) if not isinstance(param, AnyType) else NeverType()
            for param, arg in zip(self.params, args)
        ]

        if len(args) != len(self.params):
            return
        for param, arg in zip(params, args):
            typ, dim = unify(param, arg), dimcheck(param, arg)
            if not typ:
                return typ
            elif not dim:
                return dim

        return self.edit(return_type=self.return_type.complete())


@dataclass(kw_only=True, frozen=True)
class Constant(UType):
    value: T


@dataclass(frozen=True)
class DimensionType(UType):
    dim: Optional[Expression | One] = None


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


def unify(a: T, b: T) -> T | Mismatch:
    mismatch = Mismatch("type", a, b)

    if isanyofinstance((a, b), AnyType):
        return mismatch

    if isanyofinstance((a, b), NeverType):
        return [a, b][isinstance(a, NeverType)]

    if isanyofinstance((a, b), DimensionType):
        ab = [a, b]
        dimidx = int(isinstance(b, DimensionType))
        if not (isallofinstance(ab, DimensionType) or isanyofinstance(ab, NumberType)):
            ab[dimidx] = NumberType(
                typ="Number",  # type: ignore
                dim=ab[dimidx].dim,
            )
            return Mismatch("type", *ab)
        elif isanyofinstance(ab, NumberType):
            numidx = int(not dimidx)
            if not (mismatch := dimcheck(a, b)):
                return mismatch
            return ab[numidx].edit(dim=ab[dimidx].dim)
        else:
            return a

    match a, b:
        case NumberType() as a, NumberType() as b:
            return a if a.typ == b.typ else mismatch
        case ListType() as a, ListType() as b:
            content = unify(a.content, b.content)
            if isinstance(content, Mismatch):
                return content
            return (
                ListType(content=content, _meta=a._meta | b._meta)
                if content
                else mismatch
            )
        case FunctionType() as a, FunctionType() as b:
            if a.arity != b.arity:
                return mismatch
            parts = [
                (unify(x, y) if "Any" not in (x.name(), y.name()) else AnyType())
                and dimcheck(x, y)
                for x, y in zip(a.params + [a.return_type], b.params + [b.return_type])
            ]
            return a if all(parts) else mismatch

    return a if a == b else mismatch


def dimcheck(a: T, b: T) -> Literal[True] | Mismatch:
    if (
        a.name("Never", "Any")
        or b.name("Never", "Any")
        or a.dim is None
        or b.dim is None
        or a.dim == b.dim
    ):
        return True
    return Mismatch("dimension", a.dim, b.dim)


class Overload:
    def __init__(self, *functions: "FunctionType|Overload"):
        self.functions: list[FunctionType] = []
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
