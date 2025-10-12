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


@dataclass(frozen=True)
class Struct:
    fields: dict[str, NodeType | FunctionSignature]

    def __getitem__(self, key: str) -> NodeType | FunctionSignature | None:
        return self.fields.get(key)


class _types:
    Integer = NodeType(typ="Integer")
    Float = NodeType(typ="Float")
    String = NodeType(typ="String")
    Boolean = NodeType(typ="Boolean")
    List = NodeType(typ="List")


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
