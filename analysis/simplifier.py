from collections import defaultdict
from dataclasses import replace
from typing import Literal

from nodes.core import Identifier
from nodes.unit import Expression, Neg, One, Power, Product, Scalar, Sum, UnitNode
from utils import camel2snake_pattern

modes = Literal["dimension", "unit"]


def cancel(node: UnitNode | One) -> UnitNode | One:
    canceled = cancel_(node)
    if canceled is None:
        return One()
    return canceled


def cancel_(node: UnitNode | One) -> UnitNode | None:
    match node:
        case Expression():
            value = cancel(node.value)
            if value is None:
                return None
            return Expression(value=value)
        case Product() | Sum():
            values = [value for value in node.values if cancel(value)]
            if len(values) == 1:
                return values[0]
            elif len(values) == 0:
                return None
            return replace(node, values=values)
        case Neg():
            value = cancel(node.value)
            if value is None:
                return None
            return replace(node, value=value)
        case Power():
            base = cancel(node.base)
            if base is None:
                return None
            return replace(node, base=base)
        case Scalar():
            return None if not node.unit else cancel(node.unit.value)
    return node


def simplify(node: UnitNode, do_cancel: bool = True) -> Expression | One:
    simplified = Simplifier.simplify(node)
    if do_cancel:
        simplified = cancel(simplified)
    if not isinstance(simplified, (Expression, One)):
        return Expression(value=simplified)
    return simplified


class Simplifier:
    @staticmethod
    def simplify(node: UnitNode):
        name = camel2snake_pattern.sub("_", type(node).__name__).lower() + "_"

        if hasattr(Simplifier, name):
            return getattr(Simplifier, name)(node)
        elif name in ["product_", "sum_"]:
            return Simplifier._operation(node)  # type: ignore
        elif node is None:
            return None
        else:
            raise NotImplementedError(
                f"Unit type {type(node).__name__} not implemented"
            )

    @staticmethod
    def expression_(node: Expression):
        return Simplifier.simplify(node.value)

    @staticmethod
    def identifier_(node: Identifier):
        return node

    @staticmethod
    def neg_(node: Neg):
        value = Simplifier.simplify(node.value)
        if isinstance(value, One):
            return One()
        elif isinstance(value, Scalar):
            return Scalar(value=-value.value, loc=node.loc)
        return replace(node, value=value)

    @staticmethod
    def power_(node: Power):
        base = Simplifier.simplify(node.base)
        exponent = Simplifier.simplify(node.exponent)
        assert isinstance(exponent, Scalar)
        if exponent.value == 0:
            return Scalar(1)
        elif exponent.value == 1:
            return base

        match base:
            case Power():
                assert isinstance(base.exponent, Scalar)
                return replace(
                    base,
                    exponent=Scalar(
                        base.exponent.value * exponent.value, loc=base.exponent.loc
                    ),
                )
            case Product():
                return Simplifier.simplify(
                    Product(
                        [
                            Power(
                                base=value,
                                exponent=exponent,
                                loc=base.loc.merge(exponent.loc),
                            )
                            for value in base.values
                        ]
                    )
                )
            case Scalar():
                return replace(base, value=base.value**exponent.value)

        return replace(node, base=base, exponent=exponent)

    @staticmethod
    def one_(node: One):
        return node

    @staticmethod
    def scalar_(node: Scalar):
        assert node.unit is None, node.unit
        return node

    @staticmethod
    def _operation(node: Product | Sum):
        op = type(node)
        identity = 1 if op is Product else 0

        values = [Simplifier.simplify(value) for value in node.values]
        values = [value for value in values if not isinstance(value, One)]

        flat_values = []
        for v in values:
            if isinstance(v, op):
                flat_values.extend(v.values)
            else:
                flat_values.append(v)
        values = flat_values
        del flat_values

        scalars = identity
        groups: dict[UnitNode, float] = defaultdict(lambda: 0.0)
        for value in values:
            if isinstance(value, Power):
                assert isinstance(value.exponent, Scalar)
                groups[value.base] += value.exponent.value
            elif isinstance(value, Scalar):
                scalars += value.value
            else:
                groups[value] += 1

        values = [
            (
                Power(base=value, exponent=Scalar(count), loc=value.loc)
                if op is Product
                else Product([Scalar(count), value])
            )
            if count != 1
            else value
            for value, count in groups.items()
            if count != 0
        ]

        if scalars != identity:
            values.append(Scalar(scalars))

        if len(values) == 1:
            return values[0]
        elif len(values) == 0:
            return Scalar(0)
        return Product(values=values)
