from dataclasses import dataclass, field
from typing import Any


@dataclass(kw_only=True, frozen=True)
class NodeType:
    typ: str
    dimension: list = field(default_factory=list)
    dimensionless: bool = False
    value: Any = None


@dataclass(kw_only=True, frozen=True)
class FunctionSignature:
    params: list[NodeType]
    returns: NodeType

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


_numberoverload = Overload(
    FunctionSignature(params=[_types.Int, _types.Int], returns=_types.Int),
    FunctionSignature(params=[_types.Int, _types.Float], returns=_types.Float),
    FunctionSignature(params=[_types.Float, _types.Float], returns=_types.Float),
)
_bool = FunctionSignature(params=[], returns=_types.Bool)
_ops = ["add", "sub", "mul", "div", "mod", "pow", "eq", "lt", "gt", "le", "ge", "ne"]

types: dict[str, Struct] = {
    "Int": Struct({"__bool__": _bool, **{f"__{op}__": _numberoverload for op in _ops}}),
    "Float": Struct(
        {"__bool__": _bool, **{f"__{op}__": _numberoverload for op in _ops}}
    ),
    "Bool": Struct({"__bool__": _bool}),
    "Str": Struct(
        {
            "__add__": FunctionSignature(
                params=[_types.Str, _types.Str], returns=_types.Str
            ),
            "__mul__": FunctionSignature(
                params=[_types.Str, _types.Int], returns=_types.Str
            ),
        },
    ),
    "List": Struct(
        {
            "__add__": FunctionSignature(
                params=[_types.List, _types.List], returns=_types.List
            ),
            "__mul__": FunctionSignature(
                params=[_types.List, _types.Int], returns=_types.List
            ),
        },
    ),
}
