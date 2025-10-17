from dataclasses import dataclass
from typing import Any


class Maybe:
    pass


class NodeType:
    typ2: set[str]
    dimension2: set[tuple]
    dimensionless: bool
    value: Any

    def __init__(self, typ2, dimension2=set(), dimensionless2=False, value2=None):
        self.typ2 = typ2 if isinstance(typ2, set) else {typ2}
        self.dimension2 = dimension2
        self.dimensionless2 = dimensionless2
        self.value2 = value2


@dataclass(frozen=True)
class FunctionSignature:
    params: list[NodeType]
    returns: NodeType


@dataclass(frozen=True)
class Struct:
    fields: dict[str, NodeType | FunctionSignature]

    def __getitem__(self, key: str) -> NodeType | FunctionSignature | None:
        return self.fields.get(key)


class _types:
    Integer = NodeType("Integer")
    Float = NodeType("Float")
    String = NodeType("String")
    Boolean = NodeType("Boolean")
    List = NodeType("List")


types: dict[str, Struct] = {
    "Integer": Struct(
        {
            "__add__": FunctionSignature(
                params=[_types.Integer, _types.Integer], returns=_types.Integer
            ),
            "__sub__": FunctionSignature(
                params=[_types.Integer, _types.Integer], returns=_types.Integer
            ),
            "__mul__": FunctionSignature(
                params=[_types.Integer, _types.Integer], returns=_types.Integer
            ),
            "__div__": FunctionSignature(
                params=[_types.Integer, _types.Integer], returns=_types.Float
            ),
            "__mod__": FunctionSignature(
                params=[_types.Integer, _types.Integer], returns=_types.Integer
            ),
            "__pow__": FunctionSignature(
                params=[_types.Integer, _types.Integer], returns=_types.Integer
            ),
        },
    ),
    "String": Struct(
        {
            "__add__": FunctionSignature(
                params=[_types.String, _types.String], returns=_types.String
            )
        },
    ),
}
