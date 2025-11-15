from dataclasses import dataclass, field, replace
from typing import Any, Literal, Optional, Union

from typing_extensions import overload

env = {}

T = Union[
    "NoneType",
    "VarType",
    "AnyType",
    "NumberType",
    "BoolType",
    "StrType",
    "ListType",
    "FunctionType",
]


@dataclass(kw_only=True, frozen=True)
class UType:
    meta: Any = None

    @overload
    def name(self) -> str: ...
    @overload
    def name(self, name: str) -> str: ...
    def name(self, name: Optional[str] = None) -> str | bool:
        n = self.__class__.__name__.removesuffix("Type")
        if name is not None:
            return n == name
        return n

    def type(self) -> str:
        return self.name()

    def dim(self) -> list:
        return []

    def dimless(self) -> bool:
        return True

    def edit(self, **kwargs):
        return replace(self, **kwargs)

    def complete(self, value: Optional[T] = None):
        """Complete anonymous types ?T"""
        return self


class NoneType(UType):
    pass


@dataclass(kw_only=True, frozen=True)
class NumberType(UType):
    typ: Literal["Int", "Float"] = "Float"
    dimension: list = field(default_factory=list)
    dimensionless: bool = False
    value: float | int = 0

    def type(self) -> str:
        return self.typ

    def dim(self) -> list:
        return self.dimension

    @overload
    def name(self) -> str: ...
    @overload
    def name(self, name: str) -> str: ...
    def name(self, name: Optional[str] = None) -> str | bool:
        n = self.typ
        if name is not None:
            return n == name
        return n

    def dimless(self) -> bool:
        return self.dimensionless


@dataclass(kw_only=True, frozen=True)
class BoolType(UType):
    pass


@dataclass(kw_only=True, frozen=True)
class StrType(UType):
    pass


@dataclass(frozen=True)
class VarType(UType):
    _name: str

    def type(self) -> str:
        if self._name not in env:
            return "?" + self._name
        return env[self._name].type()

    def complete(self, value: Optional[T] = None):
        global env
        if value is None:
            return env.get(self._name, self)
        if self._name not in env:
            env[self._name] = value
        elif (
            not compare(value, env[self._name]) or value.dim() != env[self._name].dim()
        ):
            return self
        return value


@dataclass(kw_only=True, frozen=True)
class ListType(UType):
    content: T = field(default=None)  # type: ignore

    def __post_init__(self):
        # break circular dependency
        if self.content is None:
            object.__setattr__(self, "content", AnyType())

    def type(self) -> str:
        return f"List[{self.content.type()}]"

    def dim(self) -> list:
        return self.content.dim()

    def dimless(self) -> bool:
        return self.content.dimless()

    def complete(self, value: Optional[T] = None):
        return self.content.complete(value)


@dataclass(kw_only=True, frozen=True)
class FunctionType(UType):
    params: list[T] = field(default_factory=list)
    return_type: T = NoneType()
    param_names: list[str] = field(default_factory=list)
    unresolved: bool = field(default=False)
    _name: str = field(default="", compare=False)
    _loc: Any = field(default=None)

    def check_args(self, *args: T) -> Optional["FunctionType"]:
        global env
        env = {}
        params = [param.complete(arg) for param, arg in zip(self.params, args)]
        if len(args) == len(self.params) and all(
            compare(p, a) for p, a in zip(params, args)
        ):
            return self.edit(return_type=self.return_type.complete())


class AnyType(UType):
    _instance = None

    def __new__(cls, name: str = "any") -> "T":
        if name == "any":
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

        t = {
            "none": NoneType(),
            "number": NumberType(),
            "int": NumberType(typ="Int"),
            "float": NumberType(typ="Float"),
            "bool": BoolType(),
            "str": StrType(),
            "list": ListType(),
            "function": FunctionType(),
        }.get(name.strip().lower())

        if t is None:
            raise ValueError(f"Unknown type name: {name!r}")

        return t


def compare(a: T, b: T) -> bool:
    match a, b:
        case NumberType(), NumberType():
            return a.typ == b.typ
        case ListType(), ListType():
            return compare(a.content, b.content)
        case FunctionType(), FunctionType():
            return compare(a.return_type, b.return_type)
        case AnyType(), AnyType():
            return False
        case AnyType(), _:
            return True
        case _, AnyType():
            return True
        case _, _:
            return a.type() == b.type()


@dataclass(frozen=True)
class Dimension:
    dimension: list = field(default_factory=list)
    dimensionless: bool = False


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


_numberoverload = Overload(
    FunctionType(params=[IntType(), IntType()], return_type=IntType()),
    FunctionType(params=[IntType(), FloatType()], return_type=FloatType()),
    FunctionType(params=[FloatType(), FloatType()], return_type=FloatType()),
)


def _conv(*types):
    return {
        f"__{typ.lower()}__": FunctionType(params=[], return_type=AnyType(typ))
        for typ in types
    }


_ops = ["add", "sub", "mul", "div", "mod", "pow", "eq", "lt", "gt", "le", "ge", "ne"]

types: dict[str, Struct] = {
    "Int": Struct(
        {
            **_conv("Bool", "Str"),
            **{f"__{op}__": _numberoverload for op in _ops},
        }
    ),
    "Float": Struct(
        {
            **_conv("Bool", "Str"),
            **{f"__{op}__": _numberoverload for op in _ops},
        }
    ),
    "Bool": Struct({**_conv("Bool"), **_conv("Str")}),
    "Str": Struct(
        {
            **_conv("Bool"),
            "__add__": FunctionType(
                params=[StrType(), StrType()], return_type=StrType()
            ),
            "__mul__": FunctionType(
                params=[StrType(), IntType()], return_type=StrType()
            ),
        },
    ),
    "List": Struct(
        {
            **_conv("Bool", "Str"),
            "__add__": FunctionType(
                params=[ListType(content=VarType("T")), ListType(content=VarType("T"))],
                return_type=ListType(content=VarType("T")),
            ),
            "__mul__": FunctionType(
                params=[ListType(), IntType()], return_type=ListType()
            ),
        },
    ),
}
