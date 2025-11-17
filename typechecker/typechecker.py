import dataclasses
from typing import Optional

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
    Index,
    Integer,
    List,
    Range,
    Return,
    Slice,
    String,
    UnaryOp,
    Unit,
    UnitDefinition,
    Variable,
    WhileLoop,
)
from classes import E, ModuleMeta
from environment import Env, Namespaces
from exceptions import ConversionError, Exceptions, uNameError, uSyntaxError, uTypeError
from typechecker.analysis import simplify
from typechecker.process_types import Processor
from typechecker.types import (
    AnyType,
    BoolType,
    Dimension,
    FunctionType,
    ListType,
    NeverType,
    NoneType,
    NumberType,
    Overload,
    RangeType,
    SliceType,
    T,
    types,
    unify,
)
from typechecker.utils import _check_method, _mismatch, format_dimension
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

    def bin_op_(self, node: BinOp, env: Env) -> T:
        """Check dimensional consistency in mathematical operations"""
        left, right = [self.check(side, env=env) for side in (node.left, node.right)]

        definition = None
        for i, field in enumerate(
            [
                types[left.name()][f"__{node.op.name}__"],
                types[right.name()][f"__r{node.op.name}__"],
                types[right.name()][f"__{node.op.name}__"],
            ]
        ):
            try:
                if checked := _check_method(
                    field, *([left, right] if i < 2 else [right, left])
                ):
                    definition = checked
                    break
            except ValueError:
                pass
        else:
            self.errors.binOpTypeMismatch(node, left, right)

        assert isinstance(definition, FunctionType)
        if not isinstance(left, NumberType) or not isinstance(right, NumberType):
            return definition.return_type

        assert isinstance(left, NumberType)
        assert isinstance(right, NumberType)
        match node.op.name:
            case "add" | "sub":
                if left.dim() != right.dim():
                    self.errors.binOpMismatch(
                        node, left, right, env=env.export("dimensions")
                    )

                return left.edit(dimension=left.dimension)
            case "mul" | "div":
                if right.dimensionless and left.dimensionless:
                    return left

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

                return left.edit(dimension=dimension)
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
                            E(base=item.base, exponent=item.exponent * right.value)
                        )
                    else:
                        dimension.append(E(base=item, exponent=right.value))

                return left.edit(dimension=simplify(dimension))
            case "mod":
                if left.dimension != right.dimension:
                    self.errors.binOpMismatch(
                        node, left, right, env=env.export("dimensions")
                    )

                return left
            case _:
                raise NotImplementedError(f"BinOp {node.op.name} not implemented!")

    def block_(self, node: Block, env: Env, function: Optional[FunctionType] = None):
        if function:
            env.meta["#function"] = function  # type: ignore
        else:
            env.meta.pop("#function", None)

        returns = None

        def check_return(returns: T | None, checked: T):
            if returns is not None and (
                returns.type() != checked.type() or returns.dim() != checked.dim()
            ):
                self.errors.throw(
                    uTypeError,
                    "Function must return the same type and dimension on all paths",
                    loc=node.loc,
                )
            return checked

        checked = NoneType()
        for statement in node.body:
            checked = self.check(statement, env=env)

            if checked.meta == "#return":
                returns = check_return(returns, checked)

        returns = check_return(returns, checked)

        return returns

    def bool_op_(self, node: BoolOp, env: Env):
        left, right = [self.check(side, env=env) for side in (node.left, node.right)]

        if (
            "__bool__" not in types[left.name()].fields
            or "__bool__" not in types[right.name()].fields
        ):
            self.errors.binOpTypeMismatch(node, left, right)

        return BoolType()

    def call_(self, node: Call, env: Env):
        callee = self.check(node.callee, env=env)
        if not callee.name("Function"):
            self.errors.throw(
                uTypeError, f"'{callee.type()}' is not callable", loc=node.loc
            )

        assert isinstance(callee, FunctionType)

        if callee.unresolved == "#unresolved":
            self.errors.throw(
                uTypeError,
                f"recursive function {callee._name}() requires an explicit return type",
                loc=callee._loc,
            )

        args = {}
        i = 0
        for arg in node.args:
            if arg.name:
                if arg.name.name in args:
                    self.errors.throw(
                        uTypeError,
                        f"{callee._name}() got multiple values for argument '{arg.name.name}'",
                        loc=arg.loc,
                    )
                if arg.name.name not in callee.param_names:
                    self.errors.throw(
                        uTypeError,
                        f"{callee._name}() got an unexpected keyword argument '{arg.name.name}'",
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
                if i >= len(callee.param_names):
                    self.errors.throw(
                        uTypeError,
                        f"{callee._name}() takes {len(callee.param_names)} argument{'s' if len(callee.param_names) != 1 else ''} "
                        f"but {len(node.args)} were given",
                        loc=node.loc,
                    )
                name = callee.param_names[i]
                i += 1

            typ = self.check(arg.value, env=env)
            param = callee.params[callee.param_names.index(name)]

            if mismatch := _mismatch(typ, param):
                self.errors.throw(
                    uTypeError,
                    f"Expected parameter of {mismatch[0]} {mismatch[2]} for argument '{name}', but got {mismatch[1]}",
                    loc=arg.loc,
                )

            args[name] = typ

        return callee.return_type

    def compare_(self, node: Compare, env: Env):
        comparators = [node.left] + node.comparators
        for i in range(len(comparators) - 1):
            op, sides = node.ops[i], (comparators[i], comparators[i + 1])

            left, right = [self.check(side, env=env) for side in sides]

            def _check_field(field):
                if isinstance(field, FunctionType):
                    if field.check_args(left, right):
                        return True
                elif isinstance(field, Overload):
                    return any(func.check_args(left, right) for func in field.functions)

            for field in (
                types[left.name()][f"__{op.name}__"],
                types[right.name()][f"__r{op.name}__"],
                types[right.name()][f"__{op.name}__"],
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
                    f"'{ops[op.name]}' not supported between '{left.type()}' and '{right.type()}'",
                    loc=sides[0].loc.merge(sides[1].loc),
                )

        return BoolType()

    def conversion_(self, node: Conversion, env: Env):
        value = self.check(node.value, env=env)

        if (
            len(node.unit.unit) == 1
            and isinstance(node.unit.unit[0], Identifier)
            and node.unit.unit[0].name in types.keys()
        ):
            # type conversion
            typ = node.unit.unit[0].name
            if (
                f"__{typ.lower()}__" not in types[value.name()].fields
                and typ != value.type()
            ):
                self.errors.throw(
                    ConversionError,
                    f"Cannot convert '{value.type()}' to '{typ}'",
                    loc=node.loc,
                )
            if typ in {"Int", "Float"}:  # don't erase dimension
                return value.edit(typ=typ)
            return AnyType(typ)

        # unit conversion
        target = self.processor.unit(node.unit, env=env.copy())

        if isinstance(value, NumberType) and (value.dim() == target or value.dimless()):
            return value.edit(dimension=target)
        elif value.name("List") and (value.dim() == target or value.dimless()):
            assert isinstance(value, ListType)
            return value.edit(content=value.content.edit(dimension=target))

        self.errors.throw(
            ConversionError,
            f"Cannot convert [[bold]{format_dimension(value.dim())}[/bold]] to [[bold]{format_dimension(target)}[/bold]]",
            loc=node.loc,
        )

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
            value=Dimension(
                dimension=dimension or [node.name],
                dimensionless=dimension == [],
            ),
        )

    def for_loop_(self, node: ForLoop, env: Env):
        pass

    def function_(self, node: Function, env: Env):
        name = getattr(node.name, "name", None)
        # verify parameter and default types
        params = [
            self.processor.type(p.type.unit, env=env)  # type: ignore
            if p.type is not None
            else AnyType()
            for p in node.params
        ]
        for i, param in enumerate(node.params):
            if param.default is not None:
                default = self.check(param.default, env=env)

                if params[i].type() == "Any":
                    params[i] = default
                    continue
                if default.type() != params[i].type():
                    self.errors.throw(
                        uTypeError,
                        f"parameter '{param.name.name}' declared as type '{params[i].type()}' but defaults to '{default.type()}'",
                        loc=param.loc,
                    )
                elif default.dim() != params[i].dim():
                    self.errors.throw(
                        uTypeError,
                        f"parameter '{param.name.name}' declared as dimension [[bold]{format_dimension(params[i].dim())}[/bold]] but defaults to [[bold]{format_dimension(default.dim())}[/bold]]",
                        loc=param.loc,
                    )

        return_type = (
            self.processor.type(node.return_type.unit, env=env)  # type: ignore
            if node.return_type
            else None
        )

        signature = FunctionType(
            _name=name, _loc=node.loc.span("start", "assign"), unresolved=True
        )
        if return_type:
            signature = signature.edit(
                params=params,
                return_type=return_type,
                param_names=[param.name.name for param in node.params],
                unresolved=False,
            )

        if name is not None:
            env.set("names")(name, signature)

        new_env = env.copy()
        for i, param in enumerate(params):
            new_env.set("names")(node.params[i].name.name, param)

        if isinstance(node.body, Block):
            body = self.block_(node.body, env=new_env, function=signature)
        else:
            body = self.check(node.body, env=new_env)

        if return_type and (mismatch := _mismatch(body, return_type)):
            self.errors.throw(
                uTypeError,
                f"function body returns {mismatch[1]}, which is different from the declared return {mismatch[0]} {mismatch[2]}",
                loc=node.body.loc,
            )

        if signature.unresolved:
            signature = signature.edit(
                params=params,
                return_type=body,
                param_names=[param.name.name for param in node.params],
                unresolved=False,
            )
        if name is not None:
            env.set("names")(name, signature)

        return signature

    def identifier_(self, node: Identifier, env: Env):
        try:
            return env.get("names")(node.name)
        except KeyError:
            self.errors.nameError(node)

    def if_(self, node: If, env: Env):
        if (typ := self.check(node.condition, env=env).type()) != "Bool":
            self.errors.throw(
                uTypeError,
                f"condition must be a Boolean, got '{typ}'",
                loc=node.condition.loc,
            )

        branches = [
            self.check(branch, env=env)
            for i, branch in enumerate((node.then_branch, node.else_branch))
            if branch is not None or i == 0  # skip if else branch is None
        ]
        if len(branches) == 1:
            return branches[0]

        if mismatch := _mismatch(*branches):
            self.errors.throw(
                uTypeError,
                f"both branches must return the same {mismatch[0]}: {mismatch[1]} vs {mismatch[2]}",
                loc=node.loc,
            )

        return branches[0]

    def index_(self, node: Index, env: Env):
        value = self.check(node.iterable, env=env)
        index = self.check(node.index, env=env)
        method = types[value.name()]["__getitem__"]
        try:
            if method is None:
                raise ValueError()
            checked = _check_method(method, value, index)
        except ValueError:
            self.errors.throw(
                uTypeError,
                f"'{value.type()}' is not subscriptable",
                loc=node.loc,
            )
            return

        if checked is None:
            self.errors.throw(
                uTypeError,
                f"Invalid index type '{index.type()}' for '{value.type()}'",
                loc=node.loc,
            )
        else:
            return checked.return_type

    def list_(self, node: List, env: Env, content: T = NeverType()) -> ListType:
        for element in node.items:
            element_type = self.check(element, env=env)
            if element_type.name("Any"):
                self.errors.throw(
                    uTypeError,
                    "list elements may not be type 'Any'",
                    loc=element.loc,
                )
            if not (unified := unify(content, element_type)):
                self.errors.throw(
                    uTypeError,
                    "list elements must be of the same type",
                    loc=element.loc,
                )
            else:
                content = unified
        return ListType(content=content)

    def number_(self, node: Integer | Float, env: Env) -> NumberType:
        dimension = self.processor.unit(node.unit, env=env)
        return NumberType(
            typ=type(node).__name__.removesuffix("eger"),  # type: ignore ; 'Integer' to 'Int'
            dimension=dimension,
            dimensionless=dimension == [],
            value=float(node.value) ** float(node.exponent if node.exponent else 1),
        )

    def range_(self, node: Range, env: Env):
        for part in [node.start, node.end]:
            checked = self.check(part, env=env)
            if not checked.name("Int"):
                self.errors.throw(
                    uTypeError,
                    f"range boundary must be an integer, got '{checked.type()}'",
                    loc=part.loc,
                )
            elif not checked.dimless():
                self.errors.throw(
                    uTypeError,
                    "range boundary must be dimensionless",
                    loc=part.loc,
                )

        if node.step is not None:
            checked = self.check(node.step, env=env)
            if not checked.name("Int", "Float"):
                self.errors.throw(
                    uTypeError,
                    f"range step must be a number, got '{checked.type()}'",
                    loc=node.step.loc,
                )
            elif not checked.dimless():
                self.errors.throw(
                    uTypeError,
                    "range step must be dimensionless",
                    loc=node.step.loc,
                )

        return RangeType()

    def return_(self, node: Return, env: Env):
        return_type = None  # it will always be defined, this is just to satisfy pyright
        if "#function" not in env.meta:
            self.errors.throw(
                uSyntaxError,
                "return statement outside function",
                loc=node.loc,
            )
        else:
            return_type = env.meta["#function"].return_type

        value = self.check(node.value, env=env) if node.value else NoneType()

        if return_type and (mismatch := _mismatch(value, return_type)):
            self.errors.throw(
                uTypeError,
                f"{mismatch[1]} is different from the declared return {mismatch[0]} {mismatch[2]}",
                loc=node.loc,
            )
            pass

        return value.edit(meta="#return")

    def slice_(self, node: Slice, env: Env):
        for part in (node.start, node.stop, node.step):
            if part is not None and not (checked := self.check(part, env=env)).name(
                "Int"
            ):
                self.errors.throw(
                    uTypeError,
                    f"slice indices must be 'Int' or None, not '{checked.type()}'",
                    loc=part.loc,
                )
        return SliceType()

    def unary_op_(self, node: UnaryOp, env: Env):
        if node.op.name == "sub":
            operand = self.check(node.operand, env=env)
            if not isinstance(operand, NumberType):
                self.errors.throw(
                    uTypeError,
                    f"bad operand type for unary -: '{operand.type()}'",
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
            name=node.name.name, value=Dimension(dimension or [node.dimension])
        )

    def variable_(self, node: Variable, env: Env):
        value = self.check(node.value, env=env)

        if node.type:
            annotation = self.processor.type(node.type.unit, env=env)

            # Infer partially specified types such as List[Any] and Int
            if (
                isinstance(annotation, ListType)
                and isinstance(value, ListType)
                and annotation.content.name("Any")
            ):
                annotation = annotation.edit(content=value.content)
            elif (
                isinstance(annotation, NumberType)
                and isinstance(value, NumberType)
                and not isinstance(node.type.unit, Call)
            ):
                annotation = annotation.edit(
                    dimension=value.dimension, dimensionless=value.dimensionless
                )

            if mismatch := _mismatch(annotation, value):
                if len(annotation.dim()) > 0 and mismatch[1:] == (
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

        _hash = None
        if node.name.name in env.names:
            if mismatch := _mismatch(env.get("names")(node.name.name), value):
                self.errors.throw(
                    uNameError,
                    f"'{node.name.name}' is overwritten in an incompatible manner: {mismatch[0]} {mismatch[2]} cannot be assigned to {mismatch[1]}",
                    loc=node.loc,
                )
            _hash = env.names[node.name.name]
        env.set("names")(name=node.name.name, value=value, _hash=_hash)
        return NoneType()

    def while_loop_(self, node: WhileLoop, env: Env):
        pass

    def check(self, node, env: Env) -> T:
        match node:
            case Integer() | Float():
                return self.number_(node, env=env.copy())
            case String() | Boolean():
                name = type(node).__name__.removesuffix("ing").removesuffix("ean")

                return AnyType(name)
            case Variable() | UnitDefinition() | DimensionDefinition() | Function():
                name = camel2snake_pattern.sub("_", type(node).__name__).lower() + "_"
                return getattr(self, name)(node, env=env)
            case _:
                name = camel2snake_pattern.sub("_", type(node).__name__).lower() + "_"
                if hasattr(self, name):
                    return getattr(self, name)(node, env=env.copy())
                raise NotImplementedError(f"Type {type(node).__name__} not implemented")

    def start(self):
        env = Env(
            glob=self.namespaces,
            level=0,
            **{
                n: {k: k for k in list(self.namespaces(n).keys())}
                for n in ("names", "units", "dimensions")
            },
        )
        for node in self.ast:
            if isinstance(node, (Import, FromImport)):
                continue
            self.check(node, env=env)
