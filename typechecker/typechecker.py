import uuid

from analysis.dimchecker import Dimchecker
from analysis.simplifier import simplify
from classes import ModuleMeta
from environment import Env, Namespaces
from exceptions.exceptions import Exceptions, Mismatch
from nodes.ast import (
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
    FunctionAnnotation,
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
    Type,
    UnaryOp,
    UnitDefinition,
    Variable,
    VariableDeclaration,
    WhileLoop,
)
from nodes.unit import Expression, One, Power, Product, Scalar
from utils import camel2snake_pattern

from . import linking
from .operators import typetable
from .types import (
    AnyType,
    BoolType,
    DimensionType,
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
    unify,
)
from .utils import UnresolvedAnyParam, _check_method, nomismatch


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

        self.dimchecker = Dimchecker(module=module, namespaces=namespaces)

    def bin_op_(self, node: BinOp, env: Env, link: int) -> T:
        """Check dimensional consistency in mathematical operations"""
        left, right = [self.check(side, env=env) for side in (node.left, node.right)]

        if not (
            isinstance(left, (NumberType, DimensionType))
            and isinstance(right, (NumberType, DimensionType))
        ):
            definition = None
            methods = [
                (left, f"__{node.op.name}__"),
                (right, f"__r{node.op.name}__"),
                (right, f"__{node.op.name}__"),
            ]
            for i, field in enumerate(
                [typetable[operand.name()][method] for operand, method in methods]
            ):
                try:
                    if checked := _check_method(
                        field, *([left, right] if i < 2 else [right, left])
                    ):
                        definition = checked
                        self.namespaces.nodes[link].meta["function"] = (
                            "left" if i == 0 else "right",
                            f"{left.name().lower() if i == 0 else right.name().lower()}{methods[i][1]}",
                        )
                        break
                except ValueError:
                    pass
            else:
                self.errors.binOpMismatch(node, Mismatch("type", left, right))

            assert isinstance(definition, FunctionType)
            return definition.return_type

        return_typ = "Float" if "Float" in {left.name(), right.name()} else "Int"
        match node.op.name:
            case "add" | "sub":
                if not (mismatch := dimcheck(left, right)):
                    self.errors.binOpMismatch(node, mismatch)

                return NumberType(typ=return_typ, dim=left.dim)
            case "mul" | "div":
                if not right.dim:
                    return left
                elif not left.dim:
                    return right

                r = right.dim
                if node.op.name == "div":
                    r = Power(base=right.dim, exponent=Scalar(-1))

                dimension = simplify(Product([left.dim, r]))

                return left.edit(dim=dimension if dimension else None)
            case "pow":
                if right.dim:
                    self.errors.throw(
                        101,
                        value=f", not {right.dim}",
                        loc=self.unlink(node.right).loc,
                    )
                if not left.dim:
                    return left.edit(typ="Float")

                assert isinstance(right, NumberType)
                dimension = Power(base=left.dim, exponent=Scalar(right.value))
                dimension = simplify(dimension)
                assert dimension is not None
                return (
                    NumberType(typ="Float", dim=Expression(dimension))
                    if isinstance(left, Expression)
                    else left.edit(dim=Expression(dimension))
                )
            case "mod":
                if not (mismatch := dimcheck(left, right)):
                    self.errors.binOpMismatch(node, mismatch)

                return left
            case _:
                raise NotImplementedError(f"BinOp {node.op.name} not implemented!")

    def block_(self, node: Block, env: Env):
        returns = None

        def check_return(returns: T | None, checked: T):
            if returns is not None and not nomismatch(returns, checked):
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
            "__bool__" not in typetable[left.name()].fields
            or "__bool__" not in typetable[right.name()].fields
        ):
            self.errors.binOpMismatch(node, Mismatch("type", left, right))

        return BoolType()

    def call_(self, node: Call, env: Env):
        callee = self.check(node.callee, env=env)
        if not callee.name("Function"):
            self.errors.throw(506, type=callee, loc=node.loc)

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

            if not (mismatch := nomismatch(typ, param)):
                self.errors.throw(
                    513,
                    kind=mismatch.kind,
                    expected=mismatch.right,
                    name=name,
                    actual=mismatch.left,
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
            a != b for a, b, _ in list(args.values())
        )
        if recheck:
            # Prevent re-entering the same function body being currently typechecked.
            if "#function" in env.meta and env.meta["#function"].node == callee.node:
                if callee.unresolved:
                    _name = f"{callee._name}() " if callee._name else ""
                    self.errors.throw(
                        508 if callee.unresolved == "recursive" else 507,
                        name=_name,
                        loc=callee._loc,
                    )
                return callee.return_type

            new_env = env.copy()
            for name, arg in args.items():
                new_env.set("names")(name, arg[1], address=arg[2])
            for i, default in enumerate(callee.param_defaults):
                idx = callee.arity[0] + i
                name = callee.param_names[idx]
                if name not in args:
                    new_env.set("names")(name, default, address=callee.param_addrs[idx])
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

    def compare_(self, node: Compare, env: Env, link: int):
        node = self.unlink(node, attrs=["comparators", "ops"])
        comparators = [node.left] + node.comparators
        self.namespaces.nodes[link].meta["functions"] = []
        for i in range(len(comparators) - 1):
            op, sides = node.ops[i], (comparators[i], comparators[i + 1])

            left, right = [self.check(side, env=env) for side in sides]

            def _check_field(field):
                if isinstance(field, FunctionType):
                    if field.check_args(left, right):
                        return True
                elif isinstance(field, Overload):
                    return any(func.check_args(left, right) for func in field.functions)

            methods = [
                (left, f"__{op.name}__"),
                (right, f"__r{op.name}__"),
                (right, f"__{op.name}__"),
            ]
            for i, field in enumerate(
                [typetable[operand.name()][method] for operand, method in methods]
            ):
                if _check_field(field):
                    self.namespaces.nodes[link].meta["functions"].append(
                        (
                            "left" if i == 0 else "right",
                            f"{left.name().lower() if i == 0 else right.name().lower()}{methods[i][1]}",
                            (left.name().lower(), right.name().lower()),
                        )
                    )
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
                    left=left,
                    right=right,
                    loc=sides[0].loc.merge(sides[1].loc),
                )

        return BoolType()

    def conversion_(self, node: Conversion, env: Env):
        value = self.check(node.value, env=env)

        if isinstance(node.target, Type):
            # type conversion
            typ = node.target.name.name
            if (
                f"__{typ.lower()}__" not in typetable[value.name()].fields
                and typ != value.name()
            ):
                self.errors.throw(515, left=value, right=typ, loc=node.loc)
            if typ in {"Int", "Float"}:  # don't erase dimension
                return value.edit(typ=typ)
            return AnyType(typ)

        assert isinstance(node.target, Expression)

        # unit conversion
        target = self.dimchecker.dimensionize(node.target, mode="unit")
        target = simplify(target)

        if isinstance(value, NumberType) and (value.dim == target or not value.dim):
            return value.edit(dim=target)
        elif value.name("List") and (value.dim == target or not value.dim):
            assert isinstance(value, ListType)
            return value.edit(content=value.content.edit(dim=target))

        self.errors.throw(
            515,
            left=value.dim,
            right=target,
            loc=node.loc,
        )

    def for_loop_(self, node: ForLoop, env: Env):
        iterable = self.check(node.iterable, env=env)
        if not iterable.name("List", "Range"):
            self.errors.throw(516, type=iterable, loc=node.iterable.loc)
        if isinstance(iterable, ListType) and iterable.content.name("Never"):
            return NoneType()

        assert isinstance(iterable, (RangeType, ListType))
        value = iterable.value if isinstance(iterable, RangeType) else iterable.content

        if len(node.iterators) > 1:
            if not isinstance(value, ListType):
                self.errors.throw(
                    517,
                    type=value,
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

                if params[i].name("Any"):
                    params[i] = default
                    continue

                if not (mismatch := nomismatch(params[i], default)):
                    self.errors.throw(
                        518,
                        param=param.name.name,
                        kind=mismatch.kind,
                        expected=mismatch.left,
                        actual=mismatch.right,
                        loc=param.loc,
                    )

        return_type = (
            self.type_(node.return_type, env=env) if node.return_type else NeverType()
        )
        arity = (sum(1 for p in node.params if p.default is None), len(params))
        param_addrs = [
            f"{self.unlink(param.name).name}-{uuid.uuid4()}" for param in node.params
        ]

        signature = FunctionType(
            _name=name,
            _loc=node.loc.span("start", "assign"),
            params=params,
            param_names=[self.unlink(param.name).name for param in node.params],
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
            new_env.set("names")(
                self.unlink(node.params[i].name).name, param, address=param_addrs[i]
            )
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

        if not (mismatch := nomismatch(body, return_type)):
            self.errors.throw(
                519,
                value=mismatch.left,
                kind=mismatch.kind,
                expected=mismatch.right,
                loc=self.unlink(node.body).loc,
            )

        signature = signature.edit(
            return_type=unify(return_type, body), unresolved=None
        )
        if name is not None:
            address = env.set("names")(name, signature)
            node.meta["address"] = address

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
        condition = self.check(node.condition, env=env)
        if "__bool__" not in typetable[condition.name()].fields:
            self.errors.throw(520, type=condition, loc=node.condition.loc)

        branches = [
            self.check(branch, env=env)
            for i, branch in enumerate((node.then_branch, node.else_branch))
            if branch is not None or i == 0  # skip if else branch is None
        ]
        if len(branches) == 1:
            return branches[0]

        if not (mismatch := nomismatch(*branches)):
            self.errors.throw(
                521,
                kind=mismatch.kind,
                then=mismatch.left,
                else_=mismatch.right,
                loc=node.loc,
            )

        return unify(*branches)

    def index_(self, node: Index, env: Env):
        value = self.check(node.iterable, env=env)
        index = self.check(node.index, env=env)

        if index.dim:
            self.errors.throw(
                537,
                dimension=index.dim,
                loc=node.loc,
            )

        method = typetable[value.name()]["__getitem__"]
        try:
            if method is None:
                raise ValueError()
            checked = _check_method(method, value, index)
        except ValueError:
            self.errors.throw(522, type=value, loc=node.loc)
            return

        if not checked:
            self.errors.throw(523, type=value, index=index, loc=node.loc)
            raise

        if isinstance(value, ListType) and value.content.name("Never"):
            return AnyType()
        else:
            return checked.return_type

    def list_(self, node: List, env: Env, content: T = NeverType()) -> ListType:
        for element in node.items:
            element_type = self.check(element, env=env)
            if element_type.name("Any"):
                self.errors.throw(524, loc=self.unlink(element, ["loc"]).loc)

            if not (mismatch := nomismatch(content, element_type)):
                self.errors.throw(
                    525, kind=mismatch.kind, loc=self.unlink(element, ["loc"]).loc
                )

            content = unify(content, element_type)  # type: ignore
        return ListType(content=content)

    def number_(self, node: Integer | Float, env: Env) -> NumberType:
        dimension = simplify(self.dimchecker.dimensionize(node.unit, mode="unit"))
        assert dimension is None or isinstance(dimension, (Expression, One)), node
        return NumberType(
            typ=type(node).__name__.removesuffix("eger"),  # type: ignore ; 'Integer' to 'Int'
            dim=dimension if dimension is not None else One(),
            value=float(node.value) ** float(node.exponent if node.exponent else 1),
        )

    def range_(self, node: Range, env: Env):
        value = NumberType(typ="Int")
        for part in [node.start, node.end]:
            checked = self.check(part, env=env)
            if not checked.name("Int"):
                self.errors.throw(526, type=checked, loc=self.unlink(part, ["loc"]).loc)
            elif checked.dim:
                self.errors.throw(527, loc=self.unlink(part, ["loc"]).loc)

        if node.step is not None:
            value = self.check(node.step, env=env)
            if not value.name("Int", "Float"):
                self.errors.throw(
                    528, type=value, loc=self.unlink(node.step, ["loc"]).loc
                )
            elif value.dim:
                self.errors.throw(529, loc=self.unlink(node.step, ["loc"]).loc)

        assert isinstance(value, NumberType)
        return RangeType(value=NumberType(typ=value.typ))

    def return_(self, node: Return, env: Env):
        if "#function" not in env.meta:
            self.errors.throw(530, loc=node.loc)
        return_type = env.meta["#function"].return_type

        value = self.check(node.value, env=env) if node.value else NoneType()

        if return_type and (not (mismatch := nomismatch(value, return_type))):
            self.errors.throw(
                519,
                value=mismatch.left,
                kind=mismatch.kind,
                expected=mismatch.right,
                loc=node.loc,
            )

        value.meta("#return", True)
        return value

    def slice_(self, node: Slice, env: Env):
        for part in (node.start, node.stop, node.step):
            if part is not None and not (checked := self.check(part, env=env)).name(
                "Int"
            ):
                self.errors.throw(532, type=checked, loc=part.loc)
        return SliceType()

    def type_(self, node: Type | Expression | FunctionAnnotation | One, env: Env):
        if isinstance(node, linking.Link):
            node = self.unlink(node)
        match node:
            case FunctionAnnotation():
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

            case Type():
                match node.name.name:
                    case "Float" | "Int":
                        return NumberType(
                            typ=node.name.name,
                            dim=self.type_(node.param, env=env) if node.param else None,
                        )
                    case "List":
                        return ListType(
                            content=self.type_(node.param, env=env)
                            if node.param
                            else NeverType()
                        )
                    case _:
                        if node.name.name in typetable:
                            return AnyType(node.name.name)
                        self.errors.throw(504, name=node.name.name, loc=node.name.loc)
                        raise

            case Expression():
                dim = simplify(self.dimchecker.dimensionize(node))
                assert isinstance(dim, Expression)
                return DimensionType(dim)

            case One():
                return DimensionType(node)

    def unary_op_(self, node: UnaryOp, env: Env):
        if node.op.name == "sub":
            operand = self.check(node.operand, env=env)
            if not isinstance(operand, NumberType):
                self.errors.throw(533, type=operand, loc=node.loc)

            return operand
        elif node.op.name == "not":
            operand = self.check(node.operand, env=env)
            method = typetable[operand.name()]["__bool__"]
            if method is None:
                self.errors.throw(534, type=operand, loc=node.loc)
            return operand

        raise NotImplementedError(f"UnaryOp not implemented: {node.op.name}")

    def unit_(self, node: Expression, env: Env):
        pass

    def variable_(self, node: Variable, env: Env, link: int):
        value = self.check(node.value, env=env)
        name = self.unlink(node.name)

        address = None
        if name.name in env.names:
            if node.type:
                self.errors.throw(604, name=name.name, loc=node.loc)
            if not (mismatch := nomismatch(env.get("names")(name.name), value)):
                self.errors.throw(
                    535,
                    name=name.name,
                    kind=mismatch.kind,
                    value=mismatch.right,
                    declared=mismatch.left,
                    loc=node.loc,
                )
            address = env.names[name.name]

        if node.type:
            annotation = self.type_(node.type, env=env)

            # Infer partially specified List[Any]
            if (
                isinstance(annotation, ListType)
                and isinstance(value, ListType)
                and annotation.content.name("Any")
            ):
                annotation = annotation.edit(content=value.content)

            if not (mismatch := nomismatch(annotation, value)):
                self.errors.throw(
                    536,
                    name=node.name.name,
                    declared=mismatch.left,
                    kind=mismatch.kind,
                    value=mismatch.right,
                    loc=node.loc,
                )

            value = unify(annotation, value)
            assert value is not None and not isinstance(value, Mismatch)

        if not isinstance(value, FunctionType):
            value = value.edit(node=link)
        address = env.set("names")(name=name.name, value=value, address=address)
        node.meta["address"] = address
        return NoneType()

    def variable_declaration_(self, node: VariableDeclaration, env: Env):
        name = self.unlink(node.name)
        if name.name in env.names:
            self.errors.throw(604, name=name.name, loc=node.loc)

        annotation = self.type_(node.type, env=env)

        address = env.set("names")(name=name.name, value=annotation)
        node.meta["address"] = address
        return NoneType()

    def while_loop_(self, node: WhileLoop, env: Env):
        cond = self.check(node.condition, env=env.copy())

        if "__bool__" not in typetable[cond.name()].fields:
            self.errors.throw(520, type=cond.name(), loc=node.loc)

        self.check(node.body, env=env)
        return NoneType()

    def check(self, link, env: Env) -> T:
        islink = isinstance(link, linking.Link)
        node = self.namespaces.nodes[link.target] if islink else link

        match node:
            case Integer() | Float():
                ret = self.number_(node, env=env.copy())
            case String() | Boolean():
                name = type(node).__name__.removesuffix("ing").removesuffix("ean")

                ret = AnyType(name)
            case Variable() | BinOp() | Compare() | Function():
                name = camel2snake_pattern.sub("_", type(node).__name__).lower() + "_"
                ret = getattr(self, name)(node, env=env, link=link.target)
            case DimensionDefinition() | UnitDefinition() | FromImport() | Import():
                return  # type: ignore
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

        if islink and ret:
            self.namespaces.typed[link.target] = ret.name().lower()
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
