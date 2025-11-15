from dataclasses import dataclass, field, replace
from typing import Any, Literal, Optional, Union

from typing_extensions import overload

T = Union[
    "NoneType",
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
        return [1]

    def dimless(self) -> bool:
        return True

    def edit(self, **kwargs):
        return replace(self, **kwargs)


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


@dataclass(kw_only=True, frozen=True)
class FunctionType(UType):
    params: list[T] = field(default_factory=list)
    return_type: T = NoneType()
    param_names: list[str] = field(default_factory=list)
    unresolved: bool = field(default=False)
    _name: str = field(default="", compare=False)
    _loc: Any = field(default=None)

    def check_args(self, *args: T) -> bool:
        params = {param.type() for param in self.params}
        args_ = {arg.type() for arg in args}
        return len(args) == len(self.params) and params == args_


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
                params=[ListType(), ListType()], return_type=ListType()
            ),
            "__mul__": FunctionType(
                params=[ListType(), IntType()], return_type=ListType()
            ),
        },
    ),
}
