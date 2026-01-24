from dataclasses import replace

from nodes.core import Identifier
from nodes.unit import (
    Expression,
    Neg,
    Power,
    Product,
    Scalar,
    Sum,
    UnitNode,
)


def is_linear(node: UnitNode, active: bool = False) -> bool:
    match node:
        case Expression() | Neg():
            return is_linear(node.value, active)
        case Product() | Sum():
            return all(
                is_linear(value, True if isinstance(value, Sum) else active)
                for value in node.values
            )
        case Power():
            return is_linear(node.base, active) and is_linear(node.exponent, True)
        case Identifier():
            if node.name == "_":
                return not active
        case Scalar():
            if node.placeholder:
                return not active
    return True


def contains_var(node: UnitNode) -> bool:
    if isinstance(node, Identifier) and node.name == "_":
        return True
    if hasattr(node, "values"):
        return any(contains_var(v) for v in node.values)  # type: ignore
    if hasattr(node, "value"):
        return contains_var(node.value)  # type: ignore
    if isinstance(node, Power):
        return contains_var(node.base) or contains_var(node.exponent)
    return False


def contains_sum(node: UnitNode) -> bool:
    if hasattr(node, "values"):
        return isinstance(node, Sum) or any(contains_sum(v) for v in node.values)  # type: ignore
    if hasattr(node, "value"):
        return contains_sum(node.value)  # type: ignore
    if isinstance(node, Power):
        return contains_sum(node.base) or contains_sum(node.exponent)
    return False


def _to_x(node: UnitNode) -> UnitNode:
    if isinstance(node, Identifier) and node.name == "_":
        return replace(node, name="x")
    if hasattr(node, "values"):
        return replace(node, values=[_to_x(v) for v in node.values])  # type: ignore
    if hasattr(node, "value"):
        return replace(node, value=_to_x(node.value))  # type: ignore
    if isinstance(node, Power):
        return replace(node, base=_to_x(node.base), exponent=_to_x(node.exponent))
    return node
