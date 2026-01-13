from dataclasses import replace
from typing import Optional, TypeVar

from analysis.invert import invert
from classes import Header, ModuleMeta
from environment import Namespaces
from exceptions.exceptions import Exceptions
from nodes.ast import Float, Integer, UnitDefinition  #
from nodes.core import Identifier
from nodes.unit import Expression, Neg, One, Power, Product, Scalar, Sum, UnitNode
from typechecker.linking import Link

from .simplifier import Simplifier

SameType = TypeVar("SameType")


def resolve(
    units: dict[str, Expression], node: UnitNode, n: Optional[Scalar] = None
) -> Expression:
    resolved = resolve_(units, node, n or Identifier("_"))
    if not isinstance(resolved, Expression):
        return Expression(resolved)
    return resolved


def resolve_(
    units: dict[str, Expression], node: UnitNode, n: Scalar | Identifier
) -> UnitNode:
    match node:
        case Neg():
            return replace(node, value=resolve_(units, node.value, n))
        case Expression():
            return resolve_(units, node.value, n)
        case Product() | Sum():
            values = [resolve_(units, value, n) for value in node.values]
            return replace(node, values=values)
        case Power():
            base = resolve_(units, node.base, n)
            exp = resolve_(units, node.exponent, n)
            return replace(node, base=base, exponent=exp)
        case Scalar():
            unit = node.unit
            if unit:
                if not isinstance(unit.value, Identifier):
                    unit = Expression(Product([Identifier("_"), unit]))

                return resolve_(units, unit, Scalar(node.value))
            return node
        case Identifier():
            if node.name == "_":
                return n
            val = units[node.name]
            res = resolve_(units, val, n)
            return res.value if isinstance(res, Expression) else res

    return node


def linear(node: UnitNode) -> bool:
    match node:
        case Expression() | Neg():
            return linear(node.value)
        case Product() | Sum():
            return all(linear(value) for value in node.values)
        case Power():
            return linear(node.base) and linear(node.exponent)
        case Identifier():
            if node.name == "_":
                return False
    return True


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
        self.conversions: dict[str, Expression] = {}

    def number_(self, node: Integer | Float, link: int):
        if not node.unit:
            return
        value = int(node.value) if isinstance(node, Integer) else float(node.value)
        exp = int(node.exponent) if node.exponent else 1
        res = resolve(self.units, Scalar(value=value * exp, unit=node.unit))

        num = self.simplify(res, do_cancel=False)
        assert isinstance(num, Expression) and isinstance(num.value, Scalar)
        self.env.nodes[link] = replace(node, value=str(num.value))

    def unit_def_(self, unit: UnitDefinition):
        if unit.value is None or isinstance(unit.value, One):
            expr = Expression(Identifier("_"))
        else:
            expr = unit.value
            if linear(expr.value):
                val = expr.value
                if isinstance(val, Product):
                    val.values.insert(0, Identifier("_"))
                else:
                    val = Product([Identifier("_"), expr])
                expr = Expression(val)

        expr = resolve(self.units, expr)

        name = unit.name.name
        inverted = self.simplify(invert(expr), do_cancel=False)
        if isinstance(inverted, One):
            inverted = Expression(Identifier("_"))

        self.units[name] = expr
        self.conversions[name] = inverted
        self.env.units[name] = expr

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
