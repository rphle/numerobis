from __future__ import annotations

from analysis import analyze, format_dimension
from astnodes import (
    Assign,
    AstNode,
    BinOp,
    Call,
    DimensionDefinition,
    Float,
    FromImport,
    Identifier,
    Import,
    Integer,
    UnitDefinition,
)
from classes import Env, ModuleMeta, Namespaces, NodeType
from exceptions import Dimension_Mismatch, Exceptions, uNameError


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

    def dimension_def(self, node: DimensionDefinition, env: Env):
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

    def unit_def(self, node: UnitDefinition, env: Env):
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

    def bin_op(self, node: BinOp, env: Env):
        """Check dimensional consistency in addition and subtraction operations"""
        sides = [self.check(side, env=env._()) for side in (node.left, node.right)]

        if (
            node.op.name in {"plus", "minus"}
            and sides[0].dimension != sides[1].dimension
        ):
            dim_strs = [format_dimension(side.dimension) for side in sides]
            self.errors.binOpMismatch(node, dim_strs)

        return NodeType(typ=sides[0].typ, dimension=sides[0].dimension)

    def number(self, node: Integer | Float, env: Env):
        dimension, unit = self.analyze("unit")(node.unit, env=env)
        return NodeType(typ=type(node).__name__, dimension=dimension, unit=unit)

    def call(self, node: Call, env: Env):
        pass

    def assignment(self, node: Call, env: Env):
        pass

    def check(self, node, env: Env) -> NodeType:
        match node:
            case Integer() | Float():
                return self.number(node, env=env._())
            case DimensionDefinition() | UnitDefinition() | BinOp() | Call() | Assign():
                return {
                    "DimensionDefinition": self.dimension_def,
                    "UnitDefinition": self.unit_def,
                    "BinOp": self.bin_op,
                    "Call": self.call,
                    "Assign": self.assignment,
                }[type(node).__name__](node, env=env._())
            case _:
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
