from astnodes import (
    AstNode,
    BinOp,
    Block,
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
    String,
    UnaryOp,
    UnitDefinition,
    Variable,
    WhileLoop,
)
from classes import E, Env, ModuleMeta, Namespaces
from exceptions import Dimension_Mismatch, Exceptions, uNameError, uTypeError
from typechecker.analysis import analyze, simplify
from typechecker.types import FunctionSignature, NodeType, Overload, types
from typechecker.utils import format_dimension
from utils import camel2snake_pattern


class Typechecker:
    def __init__(
        self,
        ast: list[AstNode],
        module: ModuleMeta,
        namespaces: Namespaces = Namespaces(),
    ):
        self.ast = ast
        self.module = module
        self.errors = Exceptions(module=module)
        self.namespaces = namespaces

        self.analyze = analyze(module)

    def bin_op_(self, node: BinOp, env: Env) -> NodeType:
        """Check dimensional consistency in addition and subtraction operations"""
        left, right = [
            self.check(side, env=env._()) for side in (node.left, node.right)
        ]

        def _check_field(field):
            if isinstance(field, FunctionSignature):
                if field.check_args(left, right):
                    return True
            elif isinstance(field, Overload):
                return any(func.check_args(left, right) for func in field.functions)

        for field in (
            types[left.typ][f"__{node.op.name}__"],
            types[right.typ][f"__r{node.op.name}__"],
            types[right.typ][f"__{node.op.name}__"],
        ):
            if _check_field(field):
                break
        else:
            self.errors.binOpTypeMismatch(node, left, right)

        match node.op.name:
            case "add" | "sub":
                if left.dimension != right.dimension:
                    self.errors.binOpMismatch(
                        node, left, right, env=env.export("dimensions")
                    )

                return NodeType(typ=left.typ, dimension=left.dimension)
            case "mul" | "div":
                if right.dimensionless and left.dimensionless:
                    return NodeType(typ=left.typ, dimension=[], dimensionless=True)

                if node.op.name == "mul":
                    r = right.dimension
                else:
                    base = (
                        right.dimension[0]
                        if len(right.dimension) == 1
                        else right.dimension
                    )
                    r = [E(base=base, exponent=-1.0)]

                dimension = simplify(left.dimension + r)

                return NodeType(typ=left.typ, dimension=dimension)
            case "pow":
                assert right.typ in {"Float", "Integer"}
                if not right.dimensionless:
                    self.errors.throw(
                        uTypeError,
                        f"Right operand of pow must be dimensionless, got [{format_dimension(right.dimension)}]",
                        loc=node.right.loc,
                    )
                dimension = []
                for item in left.dimension:
                    if isinstance(item, E):
                        dimension.append(
                            E(base=item.base, exponent=item.exponent * right.value)
                        )
                    else:
                        dimension.append(E(base=item, exponent=right.value))

                return NodeType(
                    typ=left.typ,
                    dimension=simplify(dimension),
                )
            case "mod":
                if left.dimension != right.dimension:
                    self.errors.binOpMismatch(
                        node, left, right, env=env.export("dimensions")
                    )

                return NodeType(typ=left.typ, dimension=left.dimension)
            case _:
                raise NotImplementedError(f"BinOp {node.op.name} not implemented!")

    def block_(self, node: Block, env: Env):
        checked = None
        for statement in node.body:
            checked = self.check(statement, env=env._())

        return checked

    def bool_op_(self, node: BoolOp, env: Env):
        left, right = [
            self.check(side, env=env._()) for side in (node.left, node.right)
        ]

        if (
            "__bool__" not in types[left.typ].fields
            or "__bool__" not in types[right.typ].fields
        ):
            self.errors.binOpTypeMismatch(node, left, right)

        return NodeType(typ="Bool")

    def call_(self, node: Call, env: Env):
        pass

    def compare_(self, node: Compare, env: Env):
        comparators = [node.left] + node.comparators
        for i in range(len(comparators) - 1):
            op, sides = node.ops[i], (comparators[i], comparators[i + 1])

            left, right = [self.check(side, env=env._()) for side in sides]

            def _check_field(field):
                if isinstance(field, FunctionSignature):
                    if field.check_args(left, right):
                        return True
                elif isinstance(field, Overload):
                    return any(func.check_args(left, right) for func in field.functions)

            for field in (
                types[left.typ][f"__{op.name}__"],
                types[right.typ][f"__r{op.name}__"],
                types[right.typ][f"__{op.name}__"],
            ):
                if _check_field(field):
                    break
            else:
                ops = {
                    "eq": "==",
                    "lt": "<",
                    "gt": ">",
                    "le": "<=",
                    "ge": ">=",
                    "ne": "!=",
                }
                self.errors.throw(
                    uTypeError,
                    f"'{ops[op.name]}' not supported between '{left.typ}' and '{right.typ}'",
                    loc=sides[0].loc.merge(sides[1].loc),
                )

        return NodeType(typ="Bool")

    def conversion_(self, node: Conversion, env: Env):
        value = self.check(node.value, env=env._())

        target = self.analyze("unit")(node.unit, env=env._())

        if value.dimension != target and not value.dimensionless:
            self.errors.throw(
                Dimension_Mismatch,
                f"Cannot convert [{format_dimension(value.dimension)}] to [{format_dimension(target)}]",
                loc=node.loc,
            )

        return NodeType(typ="dimension", dimension=value.dimension)

    def dimension_definition_(self, node: DimensionDefinition, env: Env):
        """Process dimension definitions"""
        if node.name.name in env.units or node.name.name in env.dimensions:
            self.errors.throw(
                uNameError,
                f"'{node.name.name}' already defined",
                loc=node.name.loc,
            )

        dimension = []

        if node.value:
            dimension = self.analyze("dimension")(node.value, env=env)

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

    def number_(self, node: Integer | Float, env: Env):
        dimension = self.analyze("unit")(node.unit, env=env)
        return NodeType(
            typ=type(node).__name__,
            dimension=dimension,
            dimensionless=dimension == [],
            value=float(node.value) ** float(node.exponent if node.exponent else 1),
        )

    def string_(self, node: String, env: Env):
        return NodeType(
            typ="String",
            dimension=[],
            value=node.value,
        )

    def unary_op_(self, node: UnaryOp, env: Env):
        if node.op.name == "sub":
            operand = self.check(node.operand, env=env._())
            if operand.typ not in ("Integer", "Float"):
                self.errors.throw(
                    uTypeError,
                    f"bad operand type for unary -: '{operand.typ}'",
                    loc=node.loc,
                )

            return operand
        return node

    def unit_definition_(self, node: UnitDefinition, env: Env):
        """Process unit definitions with proper dimension checking"""

        if node.name.name in env.units or node.name.name in env.dimensions:
            self.errors.throw(
                uNameError,
                f"'{node.name.name}' already defined",
                loc=node.name.loc,
            )

        dimension = []

        if node.dimension and not node.value:
            dimension = self.analyze("dimension")([node.dimension], env=env)
        elif node.value:
            dimension = self.analyze("unit")(node.value, env=env)

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
            value=NodeType(typ="unit", dimension=dimension or [node.dimension]),
        )

    def variable_(self, node: Variable, env: Env):
        value = self.check(node.value, env=env._())

        if node.type:
            annotation = self.analyze("unit")(node.type, env=env)

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
            case String() | List() | Boolean():
                return NodeType(
                    typ=type(node).__name__, dimension=[], dimensionless=True
                )
            case _:
                name = camel2snake_pattern.sub("_", type(node).__name__).lower() + "_"
                if hasattr(self, name):
                    return getattr(self, name)(node, env=env._())
                raise NotImplementedError(f"Type {type(node).__name__} not implemented")

    def start(self):
        env = Env(
            glob=self.namespaces,
            level=-1,
            **{
                n: {k: k for k in list(getattr(self.namespaces, n).keys())}
                for n in ("names", "units", "dimensions")
            },
        )
        for node in self.ast:
            if isinstance(node, (Import, FromImport)):
                continue
            self.check(node, env=env)
