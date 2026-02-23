"""Unit definition preprocessing and constant expansion for compilation."""

from dataclasses import replace
from decimal import Decimal
from typing import Optional, TypeVar

from ..classes import Header, ModuleMeta
from ..environment import Namespaces
from ..exceptions.exceptions import Exceptions
from ..nodes.ast import Float, Integer, UnitDefinition
from ..nodes.core import Identifier
from ..nodes.unit import Expression, Neg, One, Power, Product, Scalar, Sum, UnitNode
from ..typechecker.linking import Link
from .invert import _to_x, invert
from .simplifier import Simplifier, cancel, cancel_
from .utils import contains_sum, is_linear

SameType = TypeVar("SameType")


class Preprocessor:
    def __init__(
        self,
        program: list[Link],
        module: ModuleMeta,
        namespaces: Namespaces = Namespaces(),
        header: Header = Header(),
        units: dict[str, Expression] = {},
    ):
        self.program = program
        self.module = module
        self.errors = Exceptions(module=module)
        self.env = namespaces
        self.header = header

        self.simplifier = Simplifier(module)
        self.simplify = self.simplifier.simplify

        self.units: dict[str, Expression] = dict(units)
        self.inverted: dict[str, Expression] = {}
        self.bases: dict[str, Expression] = {}
        self.logarithmic: set[str] = set()

    def number_(self, node: Integer | Float, link: int):
        if not node.unit:
            return
        res = self.resolve(Scalar(value=Decimal(node.value), unit=cancel(node.unit)))  # type: ignore

        num = self.simplify(res, do_cancel=False)
        assert isinstance(num, Expression) and isinstance(num.value, Scalar), repr(num)
        val = replace(node, value=str(num.value.value))

        self.env.nodes[link] = val

    def unit_def_(self, unit: UnitDefinition):
        if unit.value is None or isinstance(unit.value, One):
            expr = Expression(Identifier("_"))
        else:
            expr = unit.value
            expr = self.resolve(expr, Identifier("_"))  # type: ignore
            if is_linear(expr.value, True) and not contains_sum(expr.value):
                val = expr.value
                if isinstance(val, Product):
                    val.values.insert(0, Identifier("_"))
                else:
                    val = Product([Identifier("_"), expr])
                expr = Expression(val)

        expr = self.resolve(expr)

        name = unit.name.name

        inverted = invert(self.simplify(expr, do_cancel=False))
        inverted = self.simplify(inverted, do_cancel=False)

        if isinstance(inverted, One):
            inverted = Expression(Identifier("x"))

        self.units[name] = expr
        self.inverted[name] = inverted
        self.env.units[name] = expr

        is_sum = contains_sum(expr)

        if is_sum:
            base = One()
        else:
            base = cancel_(self.to_base(expr))
            if base is None:
                base = One()
            else:
                base = self.simplify(base)
                base = invert(base) if base else base

        self.bases[name] = Expression(_to_x(base))
        if not is_linear(expr) or is_sum:
            self.logarithmic.add(name)

    def unlink(self, link: SameType) -> SameType:
        if isinstance(link, (int, Link)):
            target = link if isinstance(link, int) else link.target
            return self.env.nodes[target]  # type: ignore
        return link

    def process(self, node, link: int = -1):
        match node:
            case Integer() | Float():
                self.number_(node, link)

    def start(self):
        for unit in self.header.units:
            self.unit_def_(unit)
        for link, node in self.env.nodes.items():
            self.process(node, link)

    def resolve(self, node: UnitNode, n: Optional[Scalar] = None) -> Expression:
        resolved = self.resolve_(node, n or Identifier("_"))
        if not isinstance(resolved, Expression):
            return Expression(resolved)
        return resolved

    def resolve_(self, node: UnitNode, n: Scalar | Identifier) -> UnitNode:
        match node:
            case Neg():
                return replace(node, value=self.resolve_(node.value, n))
            case Expression():
                return self.resolve_(node.value, n)
            case Product() | Sum():
                values = [self.resolve_(value, n) for value in node.values]
                return replace(node, values=values)
            case Power():
                base = self.resolve_(node.base, n)
                exp = self.resolve_(node.exponent, n)
                return replace(node, base=base, exponent=exp)
            case Scalar():
                unit = node.unit
                if unit:
                    value = Scalar(node.value) if not node.placeholder else n

                    base = cancel_(self.to_base(unit))
                    if not base:
                        base = Scalar(Decimal(1))

                    res = self.resolve_(
                        Product([unit, Power(base, Scalar(Decimal(-1)))]),
                        Identifier("_"),
                    )

                    is_sum = contains_sum(res)
                    if is_sum:
                        res = self.resolve_(
                            Product([unit, Scalar(Decimal(1))]),
                            Identifier("_"),
                        )

                    res = self.simplify(res, do_cancel=False)

                    if is_linear(res) and not is_sum:
                        res = Product([Identifier("_"), res])

                    res = self.resolve_(res, value)

                    return res
                return node
            case Identifier():
                if node.name == "_":
                    return n
                val = self.units[node.name]
                res = self.resolve_(val, n)
                return res.value if isinstance(res, Expression) else res

        return node

    def to_base(self, node: UnitNode) -> UnitNode:
        match node:
            case Expression() | Neg():
                return replace(node, value=self.to_base(node.value))
            case Product() | Sum():
                values = [self.to_base(value) for value in node.values]
                values = [value for value in values if not isinstance(value, Scalar)]
                return replace(node, values=values)
            case Power():
                base = self.to_base(node.base)
                exp = self.to_base(node.exponent)
                return replace(node, base=base, exponent=exp)
            case Identifier():
                value = self.units.get(node.name)
                if value is None:
                    return node
                if isinstance(value.value, Identifier) and value.value.name == "_":
                    if self.env.dimensionized[node.name]:
                        return Identifier("_")
                    else:
                        return Scalar(Decimal(1))

                return self.to_base(value)

        return node
