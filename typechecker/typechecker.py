import dataclasses

from astnodes import (
    AstNode,
    BinOp,
    Block,
    Boolean,
    BoolOp,
    Call,
    Compare,
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
    Return,
    String,
    UnaryOp,
    Unit,
    UnitDefinition,
    Variable,
    WhileLoop,
)
from classes import E, Env, ModuleMeta, Namespaces
from exceptions import (
    ConversionError,
    Exceptions,
    uNameError,
    uSyntaxError,
    uTypeError,
)
from typechecker.analysis import simplify
from typechecker.process_types import Processor
from typechecker.types import FunctionSignature, NodeType, NoneT, Overload, types
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

        self.processor = Processor(module)

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
                assert right.typ in {"Float", "Int"}
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
                            E(base=item.base, exponent=item.exponent * right.meta)
                        )
                    else:
                        dimension.append(E(base=item, exponent=right.meta))

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

    def block_(self, node: Block, env: Env, function: None | NodeType = None):
        if function:
            env.meta["#function"] = function  # type: ignore
        else:
            env.meta.pop("#function", None)

        returns = None

        def check_return(returns: NodeType | None, checked: NodeType):
            if returns is not None and (
                returns.typ != checked.typ or returns.dimension != checked.dimension
            ):
                self.errors.throw(
                    uTypeError,
                    "Function must return the same type and dimension on all paths",
                    loc=node.loc,
                )
            return checked

        checked = NoneT
        for statement in node.body:
            checked = self.check(statement, env=env._())

            if checked.meta == "#return":
                returns = check_return(returns, checked)

        returns = check_return(returns, checked)

        return returns

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
        callee = self.check(node.callee, env=env._())
        if callee.typ != "Function":
            if callee.typ == "#unresolved":
                self.errors.throw(
                    uTypeError,
                    f"recursive function {callee.meta[0]}() requires an explicit return type",
                    loc=callee.meta[1],
                )
            self.errors.throw(
                uTypeError, f"'{callee.typ}' is not callable", loc=node.loc
            )

        args = {}
        i = 0
        for arg in node.args:
            if arg.name:
                if arg.name.name in args:
                    self.errors.throw(
                        uTypeError,
                        f"{callee.meta.name}() got multiple values for argument '{arg.name.name}'",
                        loc=arg.loc,
                    )
                if arg.name.name not in callee.meta.param_names:
                    self.errors.throw(
                        uTypeError,
                        f"{callee.meta.name}() got an unexpected keyword argument '{arg.name.name}'",
                        loc=arg.loc,
                    )

                name = arg.name.name
                i = -1
            else:
                if i < 0:
                    self.errors.throw(
                        uSyntaxError,
                        "positional argument follows keyword argument",
                        loc=arg.loc,
                    )
                if i >= len(callee.meta.param_names):
                    self.errors.throw(
                        uTypeError,
                        f"{callee.meta.name}() takes {len(callee.meta.param_names)} argument{'s' if len(callee.meta.param_names) != 1 else ''} "
                        f"but {len(node.args)} were given",
                        loc=node.loc,
                    )
                name = callee.meta.param_names[i]
                i += 1

            typ = self.check(arg.value, env=env._())
            param = callee.meta.params[callee.meta.param_names.index(name)]

            if mismatch := _mismatch(typ, param):
                self.errors.throw(
                    uTypeError,
                    f"Expected parameter of {mismatch[0]} {mismatch[2]} for argument '{name}', but got {mismatch[1]}",
                    loc=arg.loc,
                )

            args[name] = typ

        return callee.meta.return_type

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

        if (
            len(node.unit.unit) == 1
            and isinstance(node.unit.unit[0], Identifier)
            and node.unit.unit[0].name in types.keys()
        ):
            # type conversion
            typ = node.unit.unit[0].name
            if f"__{typ.lower()}__" not in types[value.typ].fields and typ != value.typ:
                self.errors.throw(
                    ConversionError,
                    f"Cannot convert '{value.typ}' to '{typ}'",
                    loc=node.loc,
                )
            if typ in {"Int", "Float"}:  # don't erase dimension
                return dataclasses.replace(value, typ=typ)
            return NodeType(typ=typ)

        target = self.processor.unit(node.unit, env=env._())

        if value.dimension != target and not value.dimensionless:
            self.errors.throw(
                ConversionError,
                f"Cannot convert [[bold]{format_dimension(value.dimension)}[/bold]] to [[bold]{format_dimension(target)}[/bold]]",
                loc=node.loc,
            )

        return NodeType(typ=value.typ, dimension=target)

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
            dimension = self.processor.dimension(node.value, env=env)

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
        # verify parameter and default types
        params = [
            self.processor.type(p.type.unit, env=env)  # type: ignore
            if p.type is not None
            else NodeType(typ="Any")
            for p in node.params
        ]
        for i, param in enumerate(node.params):
            if param.default is not None:
                default = self.check(param.default, env=env._())

                if params[i].typ == "Any":
                    params[i] = default
                    continue
                if default.typ != params[i].typ:
                    self.errors.throw(
                        uTypeError,
                        f"parameter '{param.name.name}' declared as type '{params[i].typ}' but defaults to '{default.typ}'",
                        loc=param.loc,
                    )
                elif default.dimension != params[i].dimension:
                    self.errors.throw(
                        uTypeError,
                        f"parameter '{param.name.name}' declared as dimension [[bold]{format_dimension(params[i].dimension)}[/bold]] but defaults to [[bold]{format_dimension(default.dimension)}[/bold]]",
                        loc=param.loc,
                    )

        return_type = (
            self.processor.type(node.return_type.unit, env=env)  # type: ignore
            if node.return_type
            else None
        )

        signature = None
        if return_type:
            signature = NodeType(
                typ="Function",
                meta=FunctionSignature(
                    params=params,
                    return_type=return_type,
                    name=node.name.name,
                    param_names=[param.name.name for param in node.params],
                ),
            )

        env.set("names")(
            node.name.name,
            signature
            if signature
            else NodeType(typ="#unresolved", meta=(node.name.name, node.name.loc)),
        )

        new_env = env._()
        for i, param in enumerate(params):
            new_env.set("names")(node.params[i].name.name, param)

        if isinstance(node.body, Block):
            body = self.block_(
                node.body, env=new_env, function=env.get("names")(node.name.name)
            )
        else:
            body = self.check(node.body, env=new_env)

        if return_type and (mismatch := _mismatch(body, return_type)):
            self.errors.throw(
                uTypeError,
                f"function body returns {mismatch[1]}, which is different from the declared return {mismatch[0]} {mismatch[2]}",
                loc=node.body.loc,
            )

        if not signature:
            signature = NodeType(
                typ="Function",
                meta=FunctionSignature(
                    params=params,
                    return_type=body,
                    name=node.name.name,
                    param_names=[param.name.name for param in node.params],
                ),
            )
        env.set("names")(node.name.name, signature)

    def identifier_(self, node: Identifier, env: Env):
        try:
            return env.get("names")(node.name)
        except KeyError:
            self.errors.nameError(node)

    def if_(self, node: If, env: Env):
        if (typ := self.check(node.condition, env=env._()).typ) != "Bool":
            self.errors.throw(
                uTypeError,
                f"condition must be a Boolean, got '{typ}'",
                loc=node.condition.loc,
            )

        branches = [
            self.check(branch, env=env._())
            for i, branch in enumerate((node.then_branch, node.else_branch))
            if branch is not None or i == 0  # skip if else branch is None
        ]
        if len(branches) == 1:
            return branches[0]

        mismatch = ()
        if branches[0].typ != branches[1].typ:
            mismatch = ("type", *(f"'{b.typ}'" for b in branches))
        elif branches[0].dimension != branches[1].dimension:
            mismatch = (
                "dimension",
                *(f"[[bold]{format_dimension(b.dimension)}[/bold]]" for b in branches),
            )

        if mismatch:
            self.errors.throw(
                uTypeError,
                f"both branches must return the same {mismatch[0]}: {mismatch[1]} vs {mismatch[2]}",
                loc=node.loc,
            )

        return branches[0]

    def number_(self, node: Integer | Float, env: Env):
        dimension = self.processor.unit(node.unit, env=env)
        return NodeType(
            typ=type(node).__name__.removesuffix("eger"),  # 'Integer' to 'Int'
            dimension=dimension,
            dimensionless=dimension == [],
            meta=float(node.value) ** float(node.exponent if node.exponent else 1),
        )

    def return_(self, node: Return, env: Env):
        return_type = None  # it will always be defined, this is just to satisfy pyright
        if "#function" not in env.meta:
            self.errors.throw(
                uSyntaxError,
                "return statement outside function",
                loc=node.loc,
            )
        else:
            return_type = getattr(env.meta["#function"].meta, "return_type", None)

        value = self.check(node.value, env=env._()) if node.value else NoneT

        if return_type and (mismatch := _mismatch(value, return_type)):
            self.errors.throw(
                uTypeError,
                f"{mismatch[1]} is different from the declared return {mismatch[0]} {mismatch[2]}",
                loc=node.loc,
            )
            pass

        return dataclasses.replace(value, meta="#return")

    def string_(self, node: String, env: Env):
        return NodeType(
            typ="Str",
            dimension=[],
            meta=node.value,
        )

    def unary_op_(self, node: UnaryOp, env: Env):
        if node.op.name == "sub":
            operand = self.check(node.operand, env=env._())
            if operand.typ not in ("Int", "Float"):
                self.errors.throw(
                    uTypeError,
                    f"bad operand type for unary -: '{operand.typ}'",
                    loc=node.loc,
                )

            return operand
        return node

    def unit_(self, node: Unit, env: Env):
        pass

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
            dimension = self.processor.dimension([node.dimension], env=env)
        elif node.value:
            dimension = self.processor.unit(node.value, env=env)

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
                        ConversionError,
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
            annotation = self.processor.type(node.type.unit, env=env)

            if mismatch := _mismatch(annotation, value):
                if len(annotation.dimension) > 0 and mismatch[1:] == (
                    "'Float'",
                    "'Int'",
                ):
                    # fix automatically assigned Float type for dimension annotations
                    annotation = dataclasses.replace(annotation, typ="Int")
                    mismatch = _mismatch(annotation, value)

                if mismatch:
                    self.errors.throw(
                        uTypeError,
                        f"'{node.name.name}' declared as {mismatch[1]} but has {mismatch[0]} {mismatch[2]}",
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
        return NoneT

    def while_loop_(self, node: WhileLoop, env: Env):
        pass

    def check(self, node, env: Env) -> NodeType:
        match node:
            case Integer() | Float():
                return self.number_(node, env=env._())
            case String() | List() | Boolean():
                return NodeType(
                    typ=type(node)
                    .__name__.removesuffix("ing")
                    .removesuffix("ean"),  # 'String' to 'Str'; 'Boolean' to 'Bool'
                    dimension=[],
                    dimensionless=True,
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


def _mismatch(a: NodeType, b: NodeType) -> tuple[str, str, str] | None:
    if a.typ == "Any" or b.typ == "Any":
        return
    if a.typ != b.typ:
        return ("type", f"'{a.typ}'", f"'{b.typ}'")
    elif a.dimension != b.dimension:
        value = (
            "dimension",
            *(f"[[bold]{format_dimension(x.dimension)}[/bold]]" for x in [a, b]),
        )
        return value  # type: ignore
