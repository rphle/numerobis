from dataclasses import dataclass, field
from typing import Any


@dataclass(kw_only=True, frozen=True)
class NodeType:
    typ: str
    dimension: list = field(default_factory=list)
    dimensionless: bool = False
    meta: Any = None


@dataclass(kw_only=True, frozen=True)
class FunctionSignature:
    params: list[NodeType]
    return_type: NodeType
    name: str = field(default="", compare=False)
    param_names: list[str] = field(default_factory=list)

    def check_args(self, *args: NodeType) -> bool:
        params = {param.typ for param in self.params}
        args_ = {arg.typ for arg in args}
        return len(args) == len(self.params) and params == args_


class Overload:
    functions: list[FunctionSignature] = []

    def __init__(self, *functions: "FunctionSignature|Overload"):
        for func in functions:
            self.functions.extend(
                [func] if isinstance(func, FunctionSignature) else func.functions
            )


@dataclass(frozen=True)
class Struct:
    fields: dict[str, NodeType | FunctionSignature | Overload]

    def __getitem__(self, key: str) -> NodeType | FunctionSignature | Overload | None:
        return self.fields.get(key)


class _types:
    Int = NodeType(typ="Int")
    Float = NodeType(typ="Float")
    Str = NodeType(typ="Str")
    Bool = NodeType(typ="Bool")
    List = NodeType(typ="List")


NoneT = NodeType(typ="None")

_numberoverload = Overload(
    FunctionSignature(params=[_types.Int, _types.Int], return_type=_types.Int),
    FunctionSignature(params=[_types.Int, _types.Float], return_type=_types.Float),
    FunctionSignature(params=[_types.Float, _types.Float], return_type=_types.Float),
)


def _conv(*types):
    return {
        f"__{typ.lower()}__": FunctionSignature(
            params=[], return_type=NodeType(typ=typ)
        )
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
            "__add__": FunctionSignature(
                params=[_types.Str, _types.Str], return_type=_types.Str
            ),
            "__mul__": FunctionSignature(
                params=[_types.Str, _types.Int], return_type=_types.Str
            ),
        },
    ),
    "List": Struct(
        {
            **_conv("Bool", "Str"),
            "__add__": FunctionSignature(
                params=[_types.List, _types.List], return_type=_types.List
            ),
            "__mul__": FunctionSignature(
                params=[_types.List, _types.Int], return_type=_types.List
            ),
        },
    ),
}
