import dataclasses
from hashlib import md5
from typing import Any, TypeVar

from analysis.preprocessor import Preprocessor
from classes import CompiledModule, Header, ModuleMeta
from compiler.scoping import get_free_vars
from environment import Namespaces
from exceptions.exceptions import Exceptions
from nodes.ast import (
    BinOp,
    Block,
    Boolean,
    BoolOp,
    Call,
    CallArg,
    Compare,
    Conversion,
    DimensionDefinition,
    ExternDeclaration,
    Float,
    ForLoop,
    FromImport,
    Function,
    If,
    Import,
    Index,
    IndexAssignment,
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
    WhileLoop,
)
from nodes.core import AstNode, Identifier, UnitNode
from nodes.unit import Expression, Neg, Power, Product, Scalar, Sum
from typechecker.linking import Link
from typechecker.types import FunctionType, T
from utils import camel2snake_pattern

from .tstr import tstr
from .utils import BUILTINS, compile_math, ensuresuffix, mthd, strip_parens

SameType = TypeVar("SameType")


class Compiler:
    def __init__(
        self,
        program: list[Link],
        module: ModuleMeta,
        namespaces: Namespaces = Namespaces(),
        header: Header = Header(),
        imports: list[str] = [],
    ):
        self.program = program
        self.module = module
        self.errors = Exceptions(module=module)
        self.env = namespaces
        self.header = header
        self.imports = imports

        self.uid = md5(str(module.path).encode()).hexdigest()[:8]
        self.include = set(
            {
                "unidad/runtime",
                "unidad/constants",
                "unidad/utils/utils",
                "unidad/values",
                "unidad/types/bool",
                "unidad/exceptions/throw",
                "unidad/builtins/builtins",
                "unidad/units/units",
            }
        )
        self.functions: list[str] = []
        self.typedefs: list[str] = []
        self._defined_addrs: dict[str, str] = {}
        self._imported_names = {}
        self._imported_units = {}

    def bin_op_(self, node: BinOp, link: int) -> tstr:
        operands = [self.compile(node.left), self.compile(node.right)]

        out = tstr("__$func__($left, $right)")
        out["left"], out["right"] = operands[:: node.meta.get("side", 1)]
        out["func"] = node.op.name

        return out

    def block_(self, node: Block, link: int) -> tstr:
        out = []

        for stmt in node.body:
            out.append(str(self.compile(stmt)) + ";")

        return tstr("{\n" + "\n".join(out) + "\n}")

    def boolean_(self, node: Boolean, link: int) -> tstr:
        self.include.add("stdbool")
        return tstr(["VFALSE", "VTRUE"][node.value])

    def bool_op_(self, node: BoolOp, link: int) -> tstr:
        out = tstr("bool__init__(__cbool__($left) $op __cbool__($right))")

        out["left"] = self.compile(node.left)
        out["right"] = self.compile(node.right)
        out["op"] = {"and": "&&", "or": "||", "xor": "^"}[node.op.name]

        return out

    def call_(self, node: Call, link: int) -> tstr:
        out = tstr("$callee($args)")

        callee = self.compile(node.callee)
        out["callee"] = callee

        unlinked_args: list[CallArg] = [self.unlink(arg) for arg in node.args]  # type: ignore
        args = []

        # positional args
        i = 0
        for arg in unlinked_args:
            if arg.name:
                break
            args.append(arg.value)
            i += 1

        # order arguments
        arg_names = {
            self.unlink(arg.name).name: arg  # type: ignore
            for arg in unlinked_args[i:]
        }
        if "callee" in node.meta:
            signature: FunctionType = node.meta["callee"]

            for name in signature.param_names[i:]:
                args.append(arg_names[name].value if name in arg_names else None)
        else:
            args = [arg.value for arg in arg_names.values()]

        args = [str(self.compile(arg)) if arg else "NULL" for arg in args]

        str_args = f"(Value*[]){{{callee}, {', '.join(args)}}}"
        out = tstr(f"__call__({callee}, {str_args})")

        return out

    def compare_(self, node: Compare, link: int) -> tstr:
        comparators = [node.left, *node.comparators]
        values = [self.compile(c) for c in comparators]

        comparisons = []
        for i, op in enumerate(node.ops):
            opname = self.unlink(op).name  # type: ignore
            if (
                opname in ["eq", "ne"]
                and node.meta["types"][i][0] != node.meta["types"][i][1]
            ):
                return tstr("VFALSE" if opname == "eq" else "VTRUE")

            out = tstr("__$op__($left, $right)")
            operands = [values[i], values[i + 1]]

            out["left"], out["right"] = operands[:: node.meta["side"][i]]
            out["op"] = opname

            if opname == "ne":
                out["op"] = "eq"
                comparisons.append(f"(__cbool__({out}) ? VFALSE : VTRUE)")  # unary !
            else:
                comparisons.append(f"__cbool__({out})")

        return tstr(f"bool__init__({' && '.join(comparisons)})")

    def conversion_(self, node: Conversion, link: int) -> tstr:
        if not isinstance(node.target, Type):
            # unit conversion
            return self.compile(node.value)

        out = tstr("__$func__($value, $loc)")
        out["value"] = self.compile(node.value)
        out["loc"] = (
            f"LOC({node.loc.line}, {node.loc.col}, {node.loc.end_line}, {node.loc.end_col})"
        )

        out["func"] = f"{node.target.name.name.lower()}"
        return out

    def extern_declaration_(self, node: ExternDeclaration, link: int) -> tstr:
        self.include.add("unidad/extern")

        out = tstr('Value *und_$uid_$name = u_extern_lookup("$name")')
        out["uid"] = self.uid
        out["name"] = self.unlink(self.unlink(node.value).name).name  # type: ignore

        return out

    def for_loop_(self, node: ForLoop, link: int) -> tstr:
        self.include.add("unidad/types/number")  # indices
        if self._link2type(node.iterable) == "range":
            return self.for_loop_range_(node, link)

        if "value" not in node.meta:
            return tstr("// empty loop")

        loop = tstr("""for (size_t $iterator = 0; $iterator < $iterable->methods->len($iterable)->number->i64; $iterator++) {
            $iterator_defs
            $body
        }""")

        body = self.compile(self._make_block(node.body))
        loop["body"] = strip_parens(str(body), "{")

        iterable_type = self._link2type(node.iterable)
        iterator_name = f"__iterator_{abs(link)}"
        iterable_name = f"__iterable_{abs(link)}"
        loop["iterator"], loop["iterable"] = iterator_name, iterable_name
        loop["iterable_type"] = iterable_type

        iterators = [self.unlink(iterator) for iterator in node.iterators]

        if len(node.iterators) == 1:
            iterator = iterators[0]
            loop["iterator_defs"] = (
                f"Value *und_{self.uid}_{iterator.name} = "  # type: ignore
                + mthd("__getitem__", "$iterable", "int__init__($iterator, U_ONE)")
                + ";"
            )
        else:
            # if there are >1 iterators, it is guaranteed that the iterable is a list of lists
            iterrow_name = f"__iterrow_{abs(link)}"
            iterator_defs = f"Value *{iterrow_name} = {mthd('__getitem__', '$iterable', 'int__init__($iterator, U_ONE)')};"
            iterator_defs += "\n".join(
                f"Value *und_{self.uid}_{iterator.name} = "  # type: ignore
                + mthd("__getitem__", iterrow_name, f"int__init__({i}, U_ONE)")
                + ";"
                for i, iterator in enumerate(iterators)
            )
            loop["iterator_defs"] = iterator_defs

        iterable = self.compile(node.iterable)
        if "reference" not in iterable.meta:
            out = tstr("{\n$iterable_def;\n$loop}")
            out["iterable_def"] = f"Value *{iterable_name} = {iterable}"
            out["loop"] = loop
            return out
        else:
            loop["iterable"] = iterable

        return loop

    def for_loop_range_(self, node: ForLoop, link: int) -> tstr:
        loop = tstr("""{
            Range *$range = $range_def->range;
            for ($type $i = $range->start;
                (($range->step > 0) ? ($i < $range->stop) : ($i > $range->stop));
                $i += $range->step)
            {
                Value *$iv = $vtype__init__($i, U_ONE);
                $body
            }}""")

        body = self.compile(self._make_block(node.body))
        loop["body"] = strip_parens(str(body), "{")
        loop["i"] = f"__iterator_{abs(link)}"
        loop["iv"] = self.compile(node.iterators[0])

        loop["vtype"] = node.meta["value"].name().lower()  # 'int' or 'float'
        loop["type"] = {"Int": "gint64", "Float": "gdouble"}[node.meta["value"].name()]

        r = self.unlink(node.iterable)
        if not isinstance(r, Range):
            loop["range_def"] = self.compile(node.iterable)
            loop["range"] = f"__range_{abs(link)}"
            return loop

        # inline range
        assert isinstance(r, Range)
        loop = tstr(
            """{
            for ($type $i = $start;
                (($step > 0) ? ($i < $stop) : ($i > $stop));
                $i += $step)
            {
                Value *$iv = $vtype__init__($i, U_ONE);
                $body
            }}""",
            content=loop.content,
        )

        for key, value in [("start", r.start), ("stop", r.end), ("step", r.step)]:
            value = self.unlink(value)
            if value and isinstance(value, UnaryOp):
                # negative
                value = self.unlink(value.operand)
                value = dataclasses.replace(value, value=f"-{value.value}")  # type: ignore

            loop[key] = self.number_(value, init=False) if value else 1  # type: ignore

        return loop

    def function_(self, node: Function, link: int) -> tstr:
        self.include.add("unidad/closures")

        definition = tstr("""Value *$name(void *__env, Value **__args) {
                                U_UNPACK_ENV($env)
                                $shadow_vars
                                Value *self = __args[0];
                                $args

                                $body
                            }""")
        assert node.body is not None

        self._defined_addrs.update(self.env.nodes[link].meta["addrs"])
        defined_addrs = {addr: name for name, addr in self._defined_addrs.items()}

        body = self.compile(self._make_block(node.body, rtrn=True))
        body_node = self.unlink(node.body)
        if isinstance(body_node, Block) and not isinstance(body_node.body[-1], Return):
            body = str(body)[:-1] + "\nreturn NONE;\n}"

        _unlinked_params = [self.unlink(param) for param in node.params]

        params = [str(self.compile(param.name)) for param in _unlinked_params]
        free_vars = [
            self._imported_names.get(var, f"und_{self.uid}_") + var
            for var in get_free_vars(
                self.env.nodes, node, link=link, defined_addrs=defined_addrs
            )
        ]
        env_type = f"__Env_{self.uid}_{abs(link)}"

        definition["body"] = strip_parens(str(body), "{")
        definition["name"] = f"__impl_{self.uid}_{abs(link)}"
        definition["env"] = env_type

        definition["shadow_vars"] = "\n".join(
            f"U_SHADOW_VAR({var})" for var in free_vars
        )
        definition["args"] = "\n".join(
            f"U_UNPACK_ARG({param}, {i + 1})"
            if not _unlinked_params[i].default
            else f"U_UNPACK_OPT_ARG({param}, {i + 1}, {self.compile(_unlinked_params[i].default)})"
            for i, param in enumerate(params)
        )

        self.functions.append(str(definition))

        out = f"U_NEW_CLOSURE({definition['name']}, {env_type} {', ' + ', '.join([] + free_vars) if free_vars else ''})"
        if node.name is not None:
            out = f"Value *{self.compile(node.name)} = {out}"

        self.typedefs.append(
            "typedef struct { "
            + "".join(f"Value *{v}; " for v in free_vars)
            + f"}} {env_type};"
        )

        return tstr(out)

    def identifier_(self, node: Identifier, link: int) -> tstr:
        if "link" in node.meta:
            # function name in its own body
            return tstr("self", meta={"reference": True})

        prefix = self._imported_names.get(node.name, f"und_{self.uid}_")
        return tstr(prefix + node.name, meta={"reference": True})

    def if_(self, node: If, link: int) -> tstr:
        if node.expression:
            out = tstr("(__cbool__($condition) ? ($then) : ($else))")
        else:
            out = tstr("if (__cbool__($condition)) { $then }") + (
                tstr("else { $else }") if node.else_branch else ""
            )

        out["condition"] = self.compile(node.condition)
        old_defined_addrs = self._defined_addrs.copy()
        out["then"] = self.compile(node.then_branch)
        self._defined_addrs = old_defined_addrs
        out["else"] = self.compile(node.else_branch) if node.else_branch else ""

        if not node.expression:
            out["then"] = ensuresuffix(str(out["then"]), ";")  # type: ignore
            out["else"] = ensuresuffix(str(out["else"]), ";")  # type: ignore

        return out

    def index_(self, node: Index, link: int) -> tstr:
        if self._link2type(node.index) == "slice":
            return self.slice_(node, link)

        if (iterable_type := self._link2type(node.iterable)) not in ("any", "never"):
            self.include.add(f"unidad/types/{iterable_type}")

        out = tstr("__getitem__($iterable, $index, $loc)")
        out["index"] = str(self.compile(node.index))
        out["iterable"] = str(self.compile(node.iterable))

        loc = self.unlink(node.index).loc
        out["loc"] = f"LOC({loc.line}, {loc.col}, {loc.end_line}, {loc.end_col})"

        return out

    def index_assignment_(self, node: IndexAssignment, link: int) -> tstr:
        out = tstr("__setitem__($target, $index, $value, $loc)")
        target: Index = self.unlink(node.target)  # type: ignore

        out["target"] = str(self.compile(target.iterable))
        out["index"] = str(self.compile(target.index))
        out["value"] = str(self.compile(node.value))

        loc = self.unlink(target.index).loc
        out["loc"] = f"LOC({loc.line}, {loc.col}, {loc.end_line}, {loc.end_col})"

        return out

    def list_(self, node: List, link: int) -> tstr:
        self.include.add("unidad/types/list")
        self.include.add("unidad/types/number")  # list.c includes number.h
        out = tstr("list_of($items)")

        out["items"] = ", ".join(
            [str(self.compile(item)) for item in node.items] + ["NULL"]
        )

        return out

    def number_(self, node: Integer | Float, *, init: bool = True) -> tstr:
        self.include.add("unidad/types/number")
        out = tstr("$type__init__($value, $unit)") if init else tstr("$value")

        value = node.value
        typ = "float"
        if "." not in str(value) and "." not in str(node.exponent):
            out["value"] = (
                f"G_GINT64_CONSTANT({value}{f'E{node.exponent}' if node.exponent else ''})"
            )
            typ = "int"
        elif not node.exponent:
            out["value"] = str(value)
        else:
            out["value"] = f"{value}E{node.exponent}"

        if init:
            out["type"] = typ
            unit = self.unit_(node.unit)
            out["unit"] = unit if unit else "U_ONE"

        return out

    def range_(self, node: Range, link: int) -> tstr:
        self.include.add("unidad/types/range")
        start, stop, step = (
            self.compile(node.start),
            self.compile(node.end),
            self.compile(node.step) if node.step else "1",
        )
        start, stop, step = [
            str(x)
            .removeprefix("int__init__(")
            .removeprefix("float__init__(")
            .removesuffix(")")
            .replace(", U_ONE", "")
            .strip()
            for x in [start, stop, step]
        ]
        return tstr(
            f"range__init__((Range){{ .start = {start}, .stop = {stop}, .step = {step} }})"
        )

    def return_(self, node: Return, link: int) -> tstr:
        return tstr(f"return {self.compile(node.value)}")

    def slice_(self, node: Index, link: int) -> tstr:
        index = self.unlink(node.index)
        assert isinstance(index, Slice)
        out = tstr("__getslice__($this, $start, $stop, $step)")

        out["this"] = self.compile(node.iterable)
        out["start"] = self.compile(index.start) if index.start is not None else "NONE"
        out["stop"] = self.compile(index.stop) if index.stop is not None else "NONE"
        out["step"] = self.compile(index.step) if index.step is not None else "NONE"

        if (iterable_type := self._link2type(node.iterable)) != "any":
            self.include.add(f"unidad/types/{iterable_type}")

        return out

    def string_(self, node: String, link: int) -> tstr:
        self.include.add("unidad/types/str")
        self.include.add("unidad/types/number")  # str.c includes number.h
        return tstr(f"str__init__(g_string_new({node.value}))")

    def unary_op_(self, node: UnaryOp, link: int) -> tstr:
        self.include.add("unidad/types/bool")

        if node.op.name == "sub":
            return tstr(f"__neg__({self.compile(node.operand)})")
        elif node.op.name == "not":
            return tstr(f"(__cbool__({self.compile(node.operand)}) ? VFALSE : VTRUE)")
        else:
            raise ValueError(f"Unknown unary operator {node.op.name}")

    def unit_(self, node: UnitNode) -> str:
        match node:
            case Expression():
                return self.unit_(node.value)
            case Sum() | Product():
                op = "U_SUM" if isinstance(node, Sum) else "U_PROD"
                values = ",".join(self.unit_(v) for v in node.values)
                if not values:
                    return ""
                return f"{op}({values})"
            case Power():
                return f"U_PWR({self.unit_(node.base)}, {self.unit_(node.exponent)})"
            case Scalar():
                return f"U_NUM({node.value})"
            case Identifier():
                return f'U_ID("{node.name}")'
            case Neg():
                return f"U_NEG({self.unit_(node.value)})"
            case _:
                raise NotImplementedError(f"Unit node cannot be compiled: {type(node)}")

    def unit_def(self, node: Expression, name: str) -> None:
        out = tstr("UNIT($name, $body)")
        out["name"] = f"_{self.uid}_{name}"
        out["body"] = compile_math(node.value)

        self.functions.append(str(out))

    def variable_(self, node: Variable, link: int) -> tstr:
        out = tstr("$name = $value")
        addr = node.meta["address"]

        out["name"] = self.compile(node.name)
        out["value"] = self.compile(node.value)

        name = self.unlink(node.name).name

        if name not in self._defined_addrs:
            self._defined_addrs[name] = addr
            out = tstr("Value *") + out

        return out

    def variable_declaration_(self, node: Variable, link: int) -> tstr:
        out = tstr("Value *$name")

        out["name"] = self.compile(node.name)

        name = self.unlink(node.name).name
        self._defined_addrs[name] = node.meta["address"]

        return out

    def while_loop_(self, node: WhileLoop, link: int) -> tstr:
        out = tstr("while (__cbool__($condition)) $body")

        out["condition_type"] = str(self._link2type(node.condition))
        out["condition"] = self.compile(node.condition)
        out["body"] = self.compile(self._make_block(node.body))

        return out

    def unlink(self, link: SameType) -> SameType:
        if isinstance(link, (int, Link)):
            target = link if isinstance(link, int) else link.target
            return self.env.nodes[target]  # type: ignore
        return link

    def preprocess(self):
        self.preprocessor = Preprocessor(
            self.program,
            module=self.module,
            namespaces=self.env,
            header=self.header,
            units=self._imported_units,
        )
        self.preprocessor.start()

    def compile(self, link: Link | Any) -> tstr:
        node = self.unlink(link) if isinstance(link, Link) else link

        match node:
            case Integer() | Float():
                return self.number_(node)
            case Import() | FromImport() | DimensionDefinition() | UnitDefinition():
                return tstr("")
            case _:
                name = camel2snake_pattern.sub("_", type(node).__name__).lower() + "_"

                if hasattr(self, name):
                    return getattr(self, name)(
                        node, link=link.target if isinstance(link, Link) else -1
                    )
                else:
                    raise NotImplementedError(
                        f"AST node {type(node).__name__} not implemented"
                    )

    def start(self) -> CompiledModule:
        self.process_header()
        self.preprocess()
        self._builtins()

        code = []
        for link in self.program:
            if stmt := str(self.compile(link)):
                code.append(stmt + ";")

        code = "\n".join(code).strip()

        for name, unit in self.preprocessor.conversions.items():
            self.unit_def(unit, name)

        return CompiledModule(
            meta=self.module,
            imports=self.imports,
            include=self.include,
            code=code,
            functions=self.functions,
            typedefs=self.typedefs,
        )

    def process_header(self):
        for i, node in enumerate(self.header.imports):
            if isinstance(node, FromImport):
                uid = md5(self.imports[i].encode()).hexdigest()[:8]
                ns = self.env.imports[node.module.name]
                if node.names is None:
                    # import *
                    names = list(ns.names.keys())
                    names += ["@" + unit for unit in ns.units.keys()]
                else:
                    # import a, b, c
                    names = [name.name for name in node.names]

                self._imported_names.update(
                    {name: f"und_{uid}_" for name in names if not name.startswith("@")}
                )
                self._imported_units.update(
                    {
                        name.lstrip("@"): ns.units[name.lstrip("@")]
                        for name in names
                        if name.startswith("@") and name.lstrip("@") in ns.units
                    }
                )

    def _builtins(self):
        uid = md5("stdlib/builtins.und".encode()).hexdigest()[:8]
        self._imported_names.update({name: f"und_{uid}_" for name in BUILTINS})

    def _node2type(self, node) -> T:
        return self.env.names[node.meta["address"]]

    def _link2type(self, link: int | Link | Any) -> str:
        link = link.target if isinstance(link, Link) else link
        if not isinstance(link, int):
            raise TypeError(f"Expected int, got {type(link).__name__}")
        return self.env.typed[link]

    def _make_block(self, node: AstNode, rtrn: bool = False) -> Block:
        if isinstance(self.unlink(node), Block):
            return node  # type: ignore
        return Block(body=[Return(value=node)]) if rtrn else Block(body=[node])
