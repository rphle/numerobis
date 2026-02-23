"""Dimensional consistency checking and unit validation for expressions."""

import re
from dataclasses import replace
from typing import Literal, Optional

from ..classes import Header
from ..environment import Namespaces
from ..exceptions.exceptions import Exceptions, ModuleMeta
from ..nodes.ast import DimensionDefinition, UnitDefinition
from ..nodes.unit import (
    Expression,
    Identifier,
    Neg,
    One,
    Power,
    Product,
    Scalar,
    Sum,
    UnitNode,
)
from ..typechecker.operators import typetable
from ..utils import camel2snake_pattern
from .simplifier import Simplifier

modes = Literal["dimension", "unit"]


class Dimchecker:
    def __init__(
        self,
        module: ModuleMeta,
        namespaces: Namespaces,
        header: Optional[Header] = None,
    ):
        self.module = module
        self.errors = Exceptions(module=module)
        self.simplifier = Simplifier(module=module)
        self.simplify = self.simplifier.simplify

        self.env = namespaces
        self.header = header

    def start(self):
        if self.header is None:
            raise ValueError("Header is None")
        for node in self.header.dimensions:
            self._process_dimension(node)
        for node in self.header.units:
            self._process_unit(node)

    def _process_dimension(self, node: DimensionDefinition):
        if (
            node.name.name in self.env.dimensionized
            or node.name.name in self.env.dimensions
        ):
            self.errors.throw(603, name=node.name.name, loc=node.name.loc)

        if node.value:
            dimension = self.dimensionize(node.value)
        else:
            dimension = Expression(value=node.name)

        dimension = self.simplify(dimension)
        self.env.dimensions[node.name.name] = dimension  # type: ignore

    def _process_unit(self, node: UnitDefinition):
        if (
            node.name.name in self.env.dimensionized
            or node.name.name in self.env.dimensions
        ):
            self.errors.throw(603, name=node.name.name, loc=node.name.loc)

        dimension = None
        if node.dimension:
            if node.dimension.name != "1":
                if node.dimension.name not in self.env.dimensions:
                    suggestion = self.env.suggest("dimensions", node.dimension.name)
                    self.errors.throw(
                        602,
                        kind="dimension",
                        name=node.dimension.name,
                        help=f"did you mean '{suggestion}'?" if suggestion else None,
                        loc=node.dimension.loc,
                    )

                dimension = self.env.dimensions[node.dimension.name]
            else:
                dimension = One()

        value = None
        if node.value:
            value = self.dimensionize(node.value, mode="unit")
            value = self.simplify(value)

            if node.dimension and value != dimension:
                self.errors.throw(
                    704,
                    name=node.name.name,
                    expected=dimension,
                    actual=value,
                    loc=node.name.loc,
                )
            elif not node.dimension:
                dimension = value

        assert dimension is None or isinstance(dimension, (Expression, One))
        if node.dimension is None and node.value is None:
            # Independent units without dimension annotation are automatically assigned to a dimension of their Titled name,
            # as long as such a name is not already defined
            titled = node.name.name.title()
            dimension = Expression(value=Identifier(name=titled, loc=node.name.loc))
            if (
                titled in self.env.dimensionized
                or titled == node.name.name
                or not re.match(r"[a-zA-Z]", node.name.name[0])
            ):
                self.errors.throw(705, name=node.name.name, loc=node.name.loc)

            if titled not in self.env.dimensions:
                self.env.dimensions[titled] = dimension

        self.env.dimensionized[node.name.name] = dimension

    def dimensionize(self, node: UnitNode, mode: modes = "dimension") -> UnitNode:
        name = camel2snake_pattern.sub("_", type(node).__name__).lower() + "_"
        if hasattr(self, name):
            return getattr(self, name)(node, mode=mode)
        else:
            raise NotImplementedError(
                f"Unit type {type(node).__name__} not implemented"
            )

    def expression_(self, node: Expression, mode: modes = "dimension") -> Expression:
        if node.value is None or isinstance(node.value, One):
            return node
        return Expression(value=self.dimensionize(node.value, mode=mode))

    def identifier_(self, node: Identifier, mode: modes = "dimension"):
        if node.name in typetable.keys():
            self.errors.throw(503, node=node.name, actual=mode, loc=node.loc)

        if node.name == "_":
            return One()

        _mode = "dimensions" if mode == "dimension" else "dimensionized"

        if node.name not in self.env(_mode):
            suggestion = self.env.suggest(_mode, node.name)

            self.errors.throw(
                602,
                kind=mode,
                name=node.name,
                help=f"did you mean '{suggestion}'?" if suggestion else None,
                loc=node.loc,
            )

        resolved = self.env(_mode)[node.name]
        resolved = resolved.value if isinstance(resolved, Expression) else resolved
        return replace(resolved, loc=node.loc)

    def neg_(self, node: Neg, mode: modes = "dimension") -> UnitNode:
        value = self.dimensionize(node.value, mode=mode)
        if isinstance(value, Scalar):
            return replace(value, value=-value.value)
        return Neg(value=value, loc=node.loc)

    def power_(self, node: Power, mode: modes = "dimension") -> UnitNode:
        base = self.dimensionize(node.base, mode=mode)
        exponent = self.dimensionize(node.exponent, mode=mode)
        exponent = self.simplify(exponent, do_cancel=False)

        if isinstance(exponent, Expression):
            exponent = exponent.value
        if not isinstance(exponent, Scalar):
            self.errors.throw(101, value=exponent, loc=node.exponent.loc)

        if isinstance(base, Scalar) and isinstance(exponent, Scalar):
            return Scalar(
                value=base.value**exponent.value, unit=base.unit, loc=node.loc
            )
        return Power(base=base, exponent=exponent, loc=node.loc)

    def product_(self, node: Product, mode: modes = "dimension") -> Product:
        values = []
        for i, factor in enumerate(node.values):
            value = self.dimensionize(factor, mode=mode)
            if isinstance(value, Product):
                values.extend(value.values)
            else:
                values.append(value)
        return Product(values=values)

    def scalar_(self, node: Scalar, mode: modes = "dimension"):
        if node.unit is None:
            return node
        return self.dimensionize(node.unit, mode=mode)

    def sum_(self, node: Sum, mode: modes = "dimension") -> Sum:
        values = []
        for i, addend in enumerate(node.values):
            value = self.dimensionize(addend, mode=mode)
            if isinstance(value, Product):
                values.extend(value.values)
            else:
                values.append(value)
        return Sum(values=values)
