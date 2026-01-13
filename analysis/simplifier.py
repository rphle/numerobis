from collections import defaultdict
from dataclasses import replace
from typing import Literal

from classes import ModuleMeta
from exceptions.exceptions import Exceptions
from nodes.core import Identifier
from nodes.unit import Call, Expression, Neg, One, Power, Product, Scalar, Sum, UnitNode
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


class Simplifier:
    def __init__(self, module: ModuleMeta):
        self.errors = Exceptions(module)

    def simplify(self, node: UnitNode, do_cancel: bool = True) -> Expression | One:
        simplified = self._simplify(node)
        if do_cancel:
            simplified = cancel(simplified)
        if not isinstance(simplified, (Expression, One)):
            return Expression(value=simplified)
        return simplified

    def _simplify(self, node: UnitNode):
        name = camel2snake_pattern.sub("_", type(node).__name__).lower() + "_"

        if hasattr(self, name):
            return getattr(self, name)(node)
        elif name in ["product_", "sum_"]:
            return self._operation(node)  # type: ignore
        elif node is None:
            return None
        else:
            raise NotImplementedError(
                f"Unit type {type(node).__name__} not implemented"
            )

    def call_(self, node: Call):
        args = [replace(a, value=self._simplify(a.value)) for a in node.args]
        return replace(node, args=args)

    def expression_(self, node: Expression):
        return self._simplify(node.value)

    def identifier_(self, node: Identifier):
        return node

    def neg_(self, node: Neg):
        value = self._simplify(node.value)
        if isinstance(value, One):
            return One()
        elif isinstance(value, Scalar):
            return Scalar(value=-value.value, loc=node.loc)
        return replace(node, value=value)

    def power_(self, node: Power):
        base = self._simplify(node.base)
        exponent = self._simplify(node.exponent)
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
                return self._simplify(
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
                if str(base.value) == "0":
                    return base
                return replace(base, value=base.value**exponent.value)

        return replace(node, base=base, exponent=exponent)

    def one_(self, node: One):
        return node

    def scalar_(self, node: Scalar):
        return node

    def _operation(self, node: Product | Sum):
        op = type(node)
        identity = 1 if op is Product else 0

        values = [self._simplify(value) for value in node.values]
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
            if op is Sum and (not isinstance(value, Scalar) or value.unit):
                v = (
                    value.base
                    if isinstance(value, Power)
                    else value.value
                    if isinstance(value, Scalar)
                    else value
                )
                if v not in groups and len(groups) >= 1:
                    self.errors.throw(543, loc=value.loc)

            if isinstance(value, Power):
                assert isinstance(value.exponent, Scalar)
                groups[value.base] += value.exponent.value
            elif isinstance(value, Scalar):
                if op is Sum:
                    scalars += value.value
                else:
                    scalars *= value.value
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
            return Scalar(identity)
        return Product(values=values)
