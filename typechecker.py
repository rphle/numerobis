from __future__ import annotations

from analysis import analyze, format_dimension, simplify
from astnodes import (
    AstNode,
    BinOp,
    Boolean,
    Call,
    Conversion,
    DimensionDefinition,
    Float,
    ForLoop,
    FromImport,
    Function,
    Identifier,
    If,
    Import,
    Integer,
    List,
    UnaryOp,
    UnitDefinition,
    Variable,
    WhileLoop,
)
from classes import E, Env, ModuleMeta, Namespaces, NodeType
from exceptions import Dimension_Mismatch, Exceptions, uNameError
from utils import camel2snake_pattern


class Typechecker:
    def __init__(
        self,
        ast: list[AstNode],
        module: ModuleMeta,
        namespaces: Namespaces | None = None,
    ):
        self.ast = ast
        self.module = module
        self.errors = Exceptions(module=module)
        self.ns = namespaces or Namespaces()

        self.analyze = analyze(module)

    def bin_op_(self, node: BinOp, env: Env):
        """Check dimensional consistency in addition and subtraction operations"""
        left, right = [
            self.check(side, env=env._()) for side in (node.left, node.right)
        ]

        if node.op.name in {"plus", "minus"}:
            if left.dimension != right.dimension:
                dim_strs = [format_dimension(side.dimension) for side in (left, right)]
                self.errors.binOpMismatch(node, dim_strs)

            return NodeType(typ=left.typ, dimension=left.dimension)
        elif node.op.name in {"times", "divide"}:
            if node.op.name == "times":
                r = right.dimension
            else:
                r = [
                    E(
                        base=comp.base if isinstance(comp, E) else comp,
                        exponent=(comp.exponent if isinstance(comp, E) else 1) * -1,
                    )
                    for comp in right.dimension
                ]
            dimension = simplify(left.dimension + r)

            return NodeType(typ=left.typ, dimension=dimension)
        elif node.op.name == "power":
            assert right.typ in {"Float", "Integer"}
            dimension = [
                E(
                    base=comp.base if isinstance(comp, E) else comp,
                    exponent=(comp.exponent if isinstance(comp, E) else 1)
                    * right.value,
                )
                for comp in left.dimension
            ]
            return NodeType(typ=left.typ, dimension=dimension)
        else:
            raise NotImplementedError(f"BinOp {node.op.name} not implemented!")

    def boolean_(self, node: Boolean, env: Env):
        return NodeType(typ="Boolean", dimension=[], dimensionless=True)

    def call_(self, node: Call, env: Env):
        pass

    def conversion_(self, node: Conversion, env: Env):
        value = self.check(node.value, env=env._())

        target, _ = self.analyze("unit")(node.unit, env=env._())

        if value.dimension != target and not value.dimensionless:
            self.errors.throw(
                Dimension_Mismatch,
                f"Cannot convert [{format_dimension(value.dimension)}] to [{format_dimension(target)}]",
                loc=node.loc,
            )

        return NodeType(typ="dimension", dimension=value.dimension)

    def dimension_definition_(self, node: DimensionDefinition, env: Env):
        """Process dimension definitions"""
        dimension = []

        if node.value:
            dimension, _ = self.analyze("dimension")(node.value, env=env)

        env.set("dimensions")(
            name=node.name.name,
            value=NodeType(
                typ="dimension",
                dimension=dimension or [node.name],
                dimensionless=dimension == [],
            ),
        )

    def for_loop_(self, node: ForLoop, env: Env):
        pass

    def function_(self, node: Function, env: Env):
        pass

    def identifier_(self, node: Identifier, env: Env):
        try:
            return env.get("names")(node.name)
        except KeyError:
            self.errors.nameError(node)

    def if_(self, node: If, env: Env):
        pass

    def list_(self, node: List, env: Env):
        pass

    def number_(self, node: Integer | Float, env: Env):
        dimension, unit = self.analyze("unit")(node.unit, env=env)
        return NodeType(
            typ=type(node).__name__,
            dimension=dimension,
            unit=unit,
            value=float(node.value) ** float(node.exponent if node.exponent else 1),
        )

    def unary_op_(self, node: UnaryOp, env: Env):
        pass

    def unit_definition_(self, node: UnitDefinition, env: Env):
        """Process unit definitions with proper dimension checking"""
        normalized = []
        dimension = []

        if node.dimension and not node.value:
            dimension = [node.dimension]
        elif node.value:
            dimension, normalized = self.analyze("unit")(node.value, env=env)

            if node.dimension:
                if node.dimension.name not in env.dimensions:
                    suggestion = env.suggest("dimensions")(node.dimension.name)
                    self.errors.throw(
                        uNameError,
                        f"undefined dimension '{node.dimension.name}'",
                        help=f"did you mean '{suggestion}'?" if suggestion else None,
                        loc=node.dimension.loc,
                    )

                dim_info = env.get("dimensions")(node.dimension.name)

                if not dim_info.dimension:
                    # For base dimensions, the expected dimension is the dimension name itself
                    expected = [Identifier(name=node.dimension.name)]
                else:
                    expected = dim_info.dimension

                if expected != dimension and len(dimension) > 0:
                    expected_str = format_dimension(expected)
                    actual_str = format_dimension(dimension)
                    self.errors.throw(
                        Dimension_Mismatch,
                        f"unit '{node.name.name}' declared as '{node.dimension.name}' [{expected_str}] but has dimension [{actual_str}]",
                        loc=node.name.loc,
                    )

        env.set("units")(
            name=node.name.name,
            value=NodeType(
                typ="unit",
                dimension=dimension or [node.dimension],
                unit=normalized,
            ),
        )

    def variable_(self, node: Variable, env: Env):
        value = self.check(node.value, env=env._())

        if node.type:
            annotation, _ = self.analyze("unit")(node.type, env=env)

            if value.dimension != annotation:
                expected_str = format_dimension(annotation)
                actual_str = format_dimension(value.dimension)
                self.errors.throw(
                    Dimension_Mismatch,
                    f"'{node.name.name}' declared as '{format_dimension(node.type.unit)}' [{expected_str}] but has dimension [{actual_str}]",
                    loc=node.loc,
                )

        env.set("names")(
            name=node.name.name,
            value=NodeType(
                typ=value.typ,
                dimension=value.dimension,
                dimensionless=value.dimension == [],
            ),
        )

    def while_loop_(self, node: WhileLoop, env: Env):
        pass

    def check(self, node, env: Env) -> NodeType:
        match node:
            case Integer() | Float():
                return self.number_(node, env=env._())
            case _:
                name = camel2snake_pattern.sub("_", type(node).__name__).lower() + "_"
                if hasattr(self, name):
                    return getattr(self, name)(node, env=env._())
                raise NotImplementedError(f"Type {type(node).__name__} not implemented")

    def start(self):
        env = Env(
            glob=self.ns,
            level=-1,
            **{
                n: {k: k for k in list(getattr(self.ns, n).keys())}
                for n in ("names", "units", "dimensions")
            },
        )
        for node in self.ast:
            if isinstance(node, (Import, FromImport)):
                continue
            self.check(node, env=env)
