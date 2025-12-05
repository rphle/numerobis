import re
import uuid

import typechecker.linking as linking
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
    Function,
    FunctionAnnotation,
    Identifier,
    If,
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
    VariableDeclaration,
    WhileLoop,
)
from classes import E, ModuleMeta
from environment import Env, Namespaces
from exceptions.exceptions import (
    Exceptions,
)
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
    UndefinedType,
    dimcheck,
    types,
    unify,
)
from typechecker.utils import (
    UnresolvedAnyParam,
    _check_method,
    _mismatch,
    dimful,
    format_dimension,
)
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
                if not dimcheck(left, right):
                    self.errors.binOpMismatch(
                        node, left, right, env=env.export("dimensions")
                    )

                return left.edit(dim=left.dim)
            case "mul" | "div":
                if not dimful(right.dim):
                    return left
                elif not dimful(left.dim):
                    return right

                if node.op.name == "mul":
                    r = right.dim
                else:
                    base = right.dim[0] if len(right.dim) == 1 else right.dim
                    r = [E(base=base, exponent=-1.0)]

                dimension = simplify(left.dim + r)

                return left.edit(dim=dimension)
            case "pow":
                assert right.typ in {"Float", "Int"}
                if dimful(right.dim):
                    self.errors.throw(
                        101,
                        value=f", not {format_dimension(right.dim)}",
                        loc=self.unlink(node.right).loc,
                    )
                dimension = []
                for item in left.dim or []:
                    if isinstance(item, E):
                        dimension.append(
                            E(base=item.base, exponent=item.exponent * right.value)
                        )
                    else:
                        dimension.append(E(base=item, exponent=right.value))

                return left.edit(dim=simplify(dimension))
            case "mod":
                if not dimcheck(left, right):
                    self.errors.binOpMismatch(
                        node, left, right, env=env.export("dimensions")
                    )

                return left
            case _:
                raise NotImplementedError(f"BinOp {node.op.name} not implemented!")

    def block_(self, node: Block, env: Env):
        returns = None

        def check_return(returns: T | None, checked: T):
            if returns is not None and _mismatch(returns, checked):
                self.errors.throw(505, loc=node.loc)
            return checked

        for i, statement in enumerate(node.body):
            checked = self.check(statement, env=env)

            if checked.meta("#return"):
                returns = check_return(returns, checked)
            elif i == len(node.body) - 1:
                returns = check_return(returns, NoneType())

        if returns is None:
            returns = NoneType()

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
            self.errors.throw(506, type=callee.type(), loc=node.loc)

        assert isinstance(callee, FunctionType)
        if (
            callee.unresolved
            and "#function" in env.meta
            and env.meta["#function"].node == callee.node
        ):
            _name = f"{callee._name}() " if callee._name else ""
            self.errors.throw(
                508 if callee.unresolved == "recursive" else 507,
                name=_name,
                loc=callee._loc,
            )

        node = self.unlink(node, attrs=["args"])
        args: dict[str, tuple[T, T, str]] = {}
        i = 0
        for arg in node.args:
            if arg.name:
                if arg.name.name in args:
                    self.errors.throw(
                        509, name=callee._name, arg=arg.name.name, loc=arg.loc
                    )
                if arg.name.name not in callee.param_names:
                    self.errors.throw(
                        510, name=callee._name, arg=arg.name.name, loc=arg.loc
                    )

                name = arg.name.name
                i = -1
            else:
                if i < 0:
                    self.errors.throw(511, loc=arg.loc)
                if i >= len(callee.param_names):
                    self.errors.throw(
                        512,
                        name=callee._name,
                        n_params=len(callee.param_names),
                        plural="s" if len(callee.param_names) != 1 else "",
                        n_args=len(node.args),
                        loc=node.loc,
                    )
                name = callee.param_names[i]
                i += 1

            typ = self.check(arg.value, env=env)
            param = callee.params[callee.param_names.index(name)]
            adress = callee.param_addrs[callee.param_names.index(name)]

            if param.name("Any"):
                param = typ

            if mismatch := _mismatch(typ, param):
                self.errors.throw(
                    513,
                    kind=mismatch[0],
                    expected=mismatch[2],
                    name=name,
                    actual=mismatch[1],
                    loc=arg.loc,
                )

            args[name] = (param, unify(param, typ), adress)  # type: ignore
            # enable lexical scoping
            env.glob.names[adress] = args[name][1]

        if len(args) < callee.arity[0]:
            self.errors.throw(
                512,
                name=callee._name,
                n_params=len(callee.param_names),
                plural="s" if len(callee.param_names) != 1 else "",
                n_args=len(node.args),
                loc=node.loc,
            )

        if callee.node is None:
            return callee.return_type

        # Check if constraints can be updated and the function body re-checked for better inference
        recheck = callee.unresolved == "parameters" or any(
            a.type() != b.type() for a, b, _ in list(args.values())
        )
        if recheck:
            new_env = env.copy()
            for name, arg in args.items():
                new_env.set("names")(name, arg[1], adress=arg[2])
            for i, default in enumerate(callee.param_defaults):
                idx = callee.arity[0] + i
                name = callee.param_names[idx]
                if name not in args:
                    new_env.set("names")(name, default, adress=callee.param_addrs[idx])
            new_env.meta["#function"] = callee

            if callee.meta("#curried"):
                callee._meta["#curried"].update(new_env.names)
                new_env.names = callee._meta["#curried"]

            self.errors.stack.append(node.loc)
            return_type = self.check(
                self.namespaces.nodes[callee.node].body,  # type:ignore
                env=new_env,
            )
            self.errors.stack.pop()
        else:
            return_type = callee.return_type

        return return_type

    def compare_(self, node: Compare, env: Env):
        node = self.unlink(node, attrs=["comparators", "ops"])
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
                sides = [self.unlink(side) for side in sides]
                self.errors.throw(
                    514,
                    operator=ops[op.name],
                    left=left.type(),
                    right=right.type(),
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
                and typ != value.name()
            ):
                self.errors.throw(515, left=value.type(), right=typ, loc=node.loc)
            if typ in {"Int", "Float"}:  # don't erase dimension
                return value.edit(typ=typ)
            return AnyType(typ)

        # unit conversion
        target = self.processor.unit(node.unit, env=env.copy())

        if isinstance(value, NumberType) and (
            value.dim == target or not dimful(value.dim)
        ):
            return value.edit(dim=target)
        elif value.name("List") and (value.dim == target or not dimful(value.dim)):
            assert isinstance(value, ListType)
            return value.edit(content=value.content.edit(dim=target))

        self.errors.throw(
            515,
            left=f"[[bold]{format_dimension(value.dim)}[/bold]]",
            right=f"[[bold]{format_dimension(target)}[/bold]]",
            loc=node.loc,
        )

    def dimension_definition_(self, node: DimensionDefinition, env: Env):
        """Process dimension definitions"""
        if node.name.name in env.units or node.name.name in env.dimensions:
            self.errors.throw(603, name=node.name.name, loc=node.name.loc)

        dimension = []

        if node.value:
            dimension = self.processor.dimension(node.value, env=env)

        env.set("dimensions")(
            name=node.name.name,
            value=Dimension(dimension=dimension or [node.name]),
        )

    def for_loop_(self, node: ForLoop, env: Env):
        iterable = self.check(node.iterable, env=env)
        if not iterable.name("List", "Range"):
            self.errors.throw(516, type=iterable.type(), loc=node.iterable.loc)
        if isinstance(iterable, ListType) and iterable.content.name("Never"):
            return NoneType()

        assert isinstance(iterable, (RangeType, ListType))
        value = iterable.value if isinstance(iterable, RangeType) else iterable.content

        if len(node.iterators) > 1:
            if not isinstance(value, ListType):
                self.errors.throw(
                    517,
                    type=value.type(),
                    loc=node.iterators[0].loc.merge(node.iterators[-1].loc),
                )
            else:
                value = value.content

        new_env = env.copy()
        for iterator in node.iterators:
            new_env.set("names")(self.unlink(iterator, attrs=["name"]).name, value)
        self.check(node.body, env=new_env)
        return NoneType()

    def function_(self, node: Function, env: Env, link: int):
        name = getattr(node.name, "name", None)
        # verify parameter and default types
        params = [
            self.type_(_p.type, env=env)
            if (_p := self.unlink(p)).type is not None
            else AnyType(unresolved=link)
            for p in node.params
        ]
        defaults = []
        node = self.unlink(node, attrs=["params"])
        for i, param in enumerate(node.params):
            if param.default is not None:
                default = self.check(param.default, env=env)
                defaults.append(default)

                if params[i].type() == "Any":
                    params[i] = default
                    continue

                if mismatch := _mismatch(params[i], default):
                    self.errors.throw(
                        518,
                        param=param.name.name,
                        kind=mismatch[0],
                        expected=mismatch[1],
                        actual=mismatch[2],
                        loc=param.loc,
                    )

        return_type = (
            self.type_(node.return_type, env=env) if node.return_type else NeverType()
        )
        arity = (sum(1 for p in node.params if p.default is None), len(params))
        param_addrs = [f"{param.name.name}-{uuid.uuid4()}" for param in node.params]

        signature = FunctionType(
            _name=name,
            _loc=node.loc.span("start", "assign"),
            params=params,
            param_names=[param.name.name for param in node.params],
            param_addrs=param_addrs,
            param_defaults=defaults,
            return_type=return_type,
            unresolved=None if node.return_type else "recursive",
            node=link,
            arity=arity,
        )
        signature.meta("#curried", env.names)

        if name is not None:
            env.set("names")(name, signature)

        new_env = env.copy()
        for i, param in enumerate(params):
            new_env.set("names")(node.params[i].name.name, param, adress=param_addrs[i])
        new_env.meta["#function"] = signature

        try:
            body = self.check(node.body, env=new_env)
        except UnresolvedAnyParam as e:
            if str(e) == str(link):
                signature = signature.edit(unresolved="parameters")
                if name is not None:
                    env.set("names")(name, signature)
                return signature
            raise e

        if mismatch := _mismatch(body, return_type):
            self.errors.throw(
                519,
                value=mismatch[1],
                kind=mismatch[0],
                expected=mismatch[2],
                loc=self.unlink(node.body).loc,
            )

        signature = signature.edit(
            return_type=unify(return_type, body), unresolved=None
        )
        if name is not None:
            env.set("names")(name, signature)

        return signature

    def identifier_(self, node: Identifier, env: Env):
        try:
            item = env.get("names")(node.name)
        except KeyError:
            self.errors.nameError(node)
            return

        if "#function" in env.meta:
            if isinstance(item, AnyType) and item.unresolved:
                raise UnresolvedAnyParam(item.unresolved)

        if isinstance(item, UndefinedType):
            self.errors.nameError(node)
        return item

    def if_(self, node: If, env: Env):
        if (typ := self.check(node.condition, env=env).type()) != "Bool":
            self.errors.throw(520, type=typ, loc=node.condition.loc)

        branches = [
            self.check(branch, env=env)
            for i, branch in enumerate((node.then_branch, node.else_branch))
            if branch is not None or i == 0  # skip if else branch is None
        ]
        if len(branches) == 1:
            return branches[0]

        if mismatch := _mismatch(*branches):
            self.errors.throw(
                521, kind=mismatch[0], then=mismatch[1], else_=mismatch[2], loc=node.loc
            )

        return unify(*branches)

    def index_(self, node: Index, env: Env):
        value = self.check(node.iterable, env=env)
        index = self.check(node.index, env=env)

        if dimful(index.dim):
            self.errors.throw(
                537,
                dimension=f"[[bold]{format_dimension(index.dim)}[/bold]]",
                loc=node.loc,
            )

        method = types[value.name()]["__getitem__"]
        try:
            if method is None:
                raise ValueError()
            checked = _check_method(method, value, index)
        except ValueError:
            self.errors.throw(522, type=value.type(), loc=node.loc)
            return

        if checked is None:
            self.errors.throw(523, type=value.type(), index=index.type(), loc=node.loc)
        elif isinstance(value, ListType) and value.content.name("Never"):
            return AnyType()
        else:
            return checked.return_type

    def list_(self, node: List, env: Env, content: T = NeverType()) -> ListType:
        for element in node.items:
            element_type = self.check(element, env=env)
            if element_type.name("Any"):
                self.errors.throw(524, loc=self.unlink(element, ["loc"]).loc)
            if mismatch := _mismatch(content, element_type):
                self.errors.throw(
                    525, kind=mismatch[0], loc=self.unlink(element, ["loc"]).loc
                )

            content = unify(content, element_type)  # type: ignore
        return ListType(content=content)

    def number_(self, node: Integer | Float, env: Env) -> NumberType:
        dimension = self.processor.unit(node.unit, env=env)
        return NumberType(
            typ=type(node).__name__.removesuffix("eger"),  # type: ignore ; 'Integer' to 'Int'
            dim=dimension,
            value=float(node.value) ** float(node.exponent if node.exponent else 1),
        )

    def range_(self, node: Range, env: Env):
        value = NumberType(typ="Int")
        for part in [node.start, node.end]:
            checked = self.check(part, env=env)
            if not checked.name("Int"):
                self.errors.throw(
                    526, type=checked.type(), loc=self.unlink(part, ["loc"]).loc
                )
            elif dimful(checked.dim):
                self.errors.throw(527, loc=self.unlink(part, ["loc"]).loc)

        if node.step is not None:
            value = self.check(node.step, env=env)
            if not value.name("Int", "Float"):
                self.errors.throw(
                    528, type=value.type(), loc=self.unlink(node.step, ["loc"]).loc
                )
            elif dimful(value.dim):
                self.errors.throw(529, loc=self.unlink(node.step, ["loc"]).loc)

        assert isinstance(value, NumberType)
        return RangeType(value=NumberType(typ=value.typ))

    def return_(self, node: Return, env: Env):
        if "#function" not in env.meta:
            self.errors.throw(530, loc=node.loc)
        return_type = env.meta["#function"].return_type

        value = self.check(node.value, env=env) if node.value else NoneType()

        if return_type and (mismatch := _mismatch(value, return_type)):
            self.errors.throw(
                519,
                value=mismatch[1],
                kind=mismatch[0],
                expected=mismatch[2],
                loc=node.loc,
            )

        value.meta("#return", True)
        return value

    def slice_(self, node: Slice, env: Env):
        for part in (node.start, node.stop, node.step):
            if part is not None and not (checked := self.check(part, env=env)).name(
                "Int"
            ):
                self.errors.throw(532, type=checked.type(), loc=part.loc)
        return SliceType()

    def type_(self, node: Unit | FunctionAnnotation, env: Env):
        if isinstance(node, FunctionAnnotation):
            return FunctionType(
                params=[self.type_(param, env=env) for param in node.params],
                param_names=[param.name for param in node.param_names],
                param_addrs=[
                    f"{param.name}-{uuid.uuid4()}" for param in node.param_names
                ],
                return_type=self.type_(node.return_type, env=env)
                if node.return_type
                else NoneType(),
                arity=node.arity,
            )
        elif (
            len(node.unit) == 1
            and isinstance(node.unit[0], Call)
            and isinstance(node.unit[0].callee, Identifier)
            and node.unit[0].callee.name == "List"
        ):
            lst = node.unit[0].args[0]
            assert isinstance(lst.value, (Unit, FunctionAnnotation))
            return ListType(content=self.type_(lst.value, env=env))

        return self.processor.type(node.unit, env=env)

    def unary_op_(self, node: UnaryOp, env: Env):
        if node.op.name == "sub":
            operand = self.check(node.operand, env=env)
            if not isinstance(operand, NumberType):
                self.errors.throw(533, type=operand.type(), loc=node.loc)

            return operand
        elif node.op.name == "not":
            operand = self.check(node.operand, env=env)
            method = types[operand.name()]["__bool__"]
            if method is None:
                self.errors.throw(534, type=operand.type(), loc=node.loc)
            return operand

        raise NotImplementedError(f"UnaryOp not implemented: {node.op.name}")

    def unit_(self, node: Unit, env: Env):
        pass

    def unit_definition_(self, node: UnitDefinition, env: Env):
        """Process unit definitions with proper dimension checking"""

        if node.name.name in env.units or node.name.name in env.dimensions:
            self.errors.throw(603, name=node.name.name, loc=node.name.loc)

        dimension = []

        if node.dimension and not node.value:
            dimension = self.processor.dimension([node.dimension], env=env)
        elif node.value:
            dimension = self.processor.unit(node.value, env=env)

            if node.dimension:
                if node.dimension.name not in env.dimensions:
                    suggestion = env.suggest("dimensions")(node.dimension.name)
                    self.errors.throw(
                        602,
                        kind="dimension",
                        name=node.dimension.name,
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
                        704,
                        name=node.name.name,
                        dimension=node.dimension.name,
                        expected=expected_str,
                        actual=actual_str,
                        loc=node.name.loc,
                    )

        if not node.dimension and dimension == []:
            # Independent units without dimension annotation are automatically assigned to a dimension of their Titled name,
            # as long as such a name is not already defined
            titled = node.name.name.title()
            dimension = [Identifier(name=titled)]
            if (
                titled in env.units
                or titled == node.name.name
                or not re.match(r"[a-zA-Z]", node.name.name[0])
            ):
                self.errors.throw(705, name=node.name.name, loc=node.name.loc)

            if titled not in env.dimensions:
                env.set("dimensions")(
                    name=titled,
                    value=Dimension(dimension=dimension),
                )

        env.set("units")(
            name=node.name.name, value=Dimension(dimension or [node.dimension])
        )

    def variable_(self, node: Variable, env: Env, link: int):
        value = self.check(node.value, env=env)

        adress = None
        if node.name.name in env.names:
            if mismatch := _mismatch(env.get("names")(node.name.name), value):
                self.errors.throw(
                    535,
                    name=node.name.name,
                    kind=mismatch[0],
                    value=mismatch[2],
                    declared=mismatch[1],
                    loc=node.loc,
                )
            adress = env.names[node.name.name]

        if adress is not None and node.type:
            self.errors.throw(604, name=node.name.name, loc=node.loc)

        if node.type:
            annotation = self.type_(node.type, env=env)

            # Infer partially specified List[Any]
            if (
                isinstance(annotation, ListType)
                and isinstance(value, ListType)
                and annotation.content.name("Any")
            ):
                annotation = annotation.edit(content=value.content)

            if mismatch := _mismatch(annotation, value):
                if mismatch:
                    self.errors.throw(
                        536,
                        name=node.name.name,
                        declared=mismatch[1],
                        kind=mismatch[0],
                        value=mismatch[2],
                        loc=node.loc,
                    )

            value = unify(annotation, value)
            assert value is not None

        if not isinstance(value, FunctionType):
            value = value.edit(node=link)
        env.set("names")(name=node.name.name, value=value, adress=adress)
        return NoneType()

    def variable_declaration_(self, node: VariableDeclaration, env: Env):
        if node.name.name in env.names:
            self.errors.throw(604, name=node.name.name, loc=node.loc)

        env.set("names")(name=node.name.name, value=UndefinedType())
        return NoneType()

    def while_loop_(self, node: WhileLoop, env: Env):
        cond = self.check(node.condition, env=env.copy())

        if "__bool__" not in types[cond.name()].fields:
            self.errors.throw(520, type=cond.name(), loc=node.loc)

        self.check(node.body, env=env)
        return NoneType()

    def check(self, link, env: Env) -> T:
        if isinstance(link, linking.Link):
            node = self.namespaces.nodes[link.target]
        else:
            node = link

        match node:
            case Integer() | Float():
                ret = self.number_(node, env=env.copy())
            case String() | Boolean():
                name = type(node).__name__.removesuffix("ing").removesuffix("ean")

                ret = AnyType(name)
            case Variable() | UnitDefinition() | DimensionDefinition() | Function():
                name = camel2snake_pattern.sub("_", type(node).__name__).lower() + "_"
                ret = getattr(self, name)(
                    node,
                    env=env,
                    **(
                        {"link": link.target}
                        if name in ["variable_", "function_"]
                        else {}
                    ),
                )
            case _:
                name = camel2snake_pattern.sub("_", type(node).__name__).lower() + "_"
                if hasattr(self, name):
                    ret = getattr(self, name)(node, env=env.copy())
                else:
                    raise NotImplementedError(
                        f"Type {type(node).__name__} not implemented"
                    )

        if ret and isinstance(link, linking.Link) and ret.node is None:
            ret = ret.edit(node=link.target)
        return ret

    def start(self):
        self.program, self.namespaces.nodes = linking.link(self.ast)
        env = Env(
            glob=self.namespaces,
            level=0,
            **{
                n: {k: k for k in list(self.namespaces(n).keys())}
                for n in ("names", "units", "dimensions")
            },
        )
        for link in self.program:
            self.check(link, env=env)

    def unlink(self, node, attrs=None):
        return linking.unlink(self.namespaces.nodes, node, attrs)
