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
    Integer = NodeType(typ="Integer")
    Float = NodeType(typ="Float")
    String = NodeType(typ="String")
    Boolean = NodeType(typ="Boolean")
    List = NodeType(typ="List")


_numberoverload = Overload(
    FunctionSignature(params=[_types.Integer, _types.Integer], returns=_types.Integer),
    FunctionSignature(params=[_types.Integer, _types.Float], returns=_types.Float),
)

types: dict[str, Struct] = {
    "Integer": Struct(
        {
            "__add__": _numberoverload,
            "__sub__": _numberoverload,
            "__mul__": _numberoverload,
            "__div__": _numberoverload,
            "__mod__": _numberoverload,
            "__pow__": _numberoverload,
        },
    ),
    "Float": Struct(
        {
            "__add__": _numberoverload,
            "__sub__": _numberoverload,
            "__mul__": _numberoverload,
            "__div__": _numberoverload,
            "__mod__": _numberoverload,
            "__pow__": _numberoverload,
        },
    ),
    "String": Struct(
        {
            "__add__": FunctionSignature(
                params=[_types.String, _types.String], returns=_types.String
            ),
            "__mul__": FunctionSignature(
                params=[_types.String, _types.Integer], returns=_types.String
            ),
        },
    ),
    "List": Struct(
        {
            "__add__": FunctionSignature(
                params=[_types.List, _types.List], returns=_types.List
            ),
            "__mul__": FunctionSignature(
                params=[_types.List, _types.Integer], returns=_types.List
            ),
        },
    ),
}
