from decimal import Decimal

from analysis.utils import _to_x, contains_var
from nodes.core import Identifier
from nodes.unit import (
    Call,
    CallArg,
    Expression,
    Neg,
    Power,
    Product,
    Scalar,
    Sum,
    UnitNode,
)


def invert(node: UnitNode) -> UnitNode:
    """
    Inverts f(_) = y into _ = g(y).
    """
    node = node.value if isinstance(node, Expression) else node
    inverted = invert_(node, Identifier("x"))

    return Expression(inverted)


def invert_(node: UnitNode, target: UnitNode) -> UnitNode:
    match node:
        case Identifier(name="_"):
            return target

        case Product(values) | Sum(values):
            kind = type(node)

            var_i, var_node = next(
                (i, node) for i, node in enumerate(values) if contains_var(node)
            )
            others = [v for i, v in enumerate(values) if i != var_i]

            operand = others[0] if len(others) == 1 else kind(others)
            operand = _to_x(operand)

            if kind is Product:
                new_target = Product([target, Power(operand, Scalar(Decimal(-1)))])
            else:
                new_target = Sum([target, Neg(operand)])
            return invert_(var_node, new_target)

        case Power(base, exponent):
            # y = _ ^ a  => _ = y ^ (1/a)
            if contains_var(base):
                new_target = Power(target, Power(exponent, Scalar(Decimal(-1))))
                return invert_(base, new_target)

            # y = a ^ _  => _ = log(a, target)
            else:
                log_call = Call(
                    callee=Identifier("logn"),
                    args=[CallArg(None, base), CallArg(None, target)],
                )
                return invert_(exponent, log_call)

        case Neg(value):
            return invert_(value, Neg(target))

        case Expression(value):
            return invert_(value, target)

        case Scalar() | Identifier():
            return node

    raise ValueError(f"Node type {type(node)} not supported for inversion.", node)
