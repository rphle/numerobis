import dataclasses
from hashlib import md5
from typing import Any

from classes import CompiledModule, Header, ModuleMeta
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
from nodes.core import Identifier
from typechecker.linking import Link
from typechecker.types import T
from utils import camel2snake_pattern

from .tstr import tstr
from .utils import ensuresuffix, mthd, strip_parens


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
            }
        )
        self._defined_addrs = set()
        self._imported_names = {}

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

        return tstr("\n".join(out))

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

        out["callee"] = self.compile(node.callee)

        if node.meta.get("extern", None) != "function":
            # normal functions and extern macros
            unlinked_args: list[CallArg] = [self.unlink(arg) for arg in node.args]  # type: ignore
            args = []

            # positional args
            i = 0
            for arg in unlinked_args:
                if arg.name:
                    break
                args.append(arg.value)
                i += 1

            if callee_node := node.meta["callee.node"]:
                # positional arguments (with default values)
                func = self.unlink(callee_node)
                assert isinstance(func, Function)

                params = {
                    self.unlink(p.name).name: p.default  # type: ignore
                    for param in func.params[i:]
                    if (p := self.unlink(param))
                }
                arg_names = {
                    self.unlink(arg.name).name: arg  # type: ignore
                    for arg in unlinked_args[i:]
                }

                for name, param in params.items():
                    if name in arg_names:
                        args.append(
                            next(a.value for n, a in arg_names.items() if n == name)
                        )
                    else:
                        args.append(param)  # type: ignore
            else:
                # positional arguments (fallback)
                for arg in unlinked_args[i:]:
                    args.append(arg.value)

            out["args"] = ", ".join(str(self.compile(arg)) for arg in args)

        else:
            # extern functions
            if len(node.args) == 0:
                out["args"] = "NULL"
            else:
                out["args"] = (
                    "(Value*[]){"
                    + ", ".join(
                        str(self.compile(self.unlink(arg).value))  # type: ignore
                        for arg in node.args
                    )
                    + "}"
                )

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
        out = tstr("__$func__($value, $loc)")
        out["value"] = self.compile(node.value)
        out["loc"] = (
            f"LOC({node.loc.line}, {node.loc.col}, {node.loc.end_line}, {node.loc.end_col})"
        )

        if isinstance(node.target, Type):
            out["func"] = f"{node.target.name.name.lower()}"
        else:
            raise NotImplementedError("Unit conversions are not supported yet.")
        return out

    def extern_declaration_(self, node: ExternDeclaration, link: int) -> tstr:
        if node.macro:
            return tstr("")

        self.include.add("unidad/extern")

        out = tstr('UExternFn und_$uid_$name = u_extern_lookup("$name")')
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

        body = self.compile(node.body)
        loop["body"] = (
            strip_parens(str(body), "{")
            if isinstance(self.unlink(node.body), Block)
            else ensuresuffix(str(body), ";")
        )

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
                + mthd("__getitem__", "$iterable", "int__init__($iterator)")
                + ";"
            )
        else:
            # if there are >1 iterators, it is guaranteed that the iterable is a list of lists
            iterrow_name = f"__iterrow_{abs(link)}"
            iterator_defs = f"Value *{iterrow_name} = {mthd('__getitem__', '$iterable', 'int__init__($iterator)')};"
            iterator_defs += "\n".join(
                f"Value *und_{self.uid}_{iterator.name} = "  # type: ignore
                + mthd("__getitem__", iterrow_name, f"int__init__({i})")
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
                Value *$iv = $vtype__init__($i);
                $body
            }}""")

        body = self.compile(node.body)
        loop["body"] = (
            strip_parens(str(body), "{")
            if isinstance(self.unlink(node.body), Block)
            else ensuresuffix(str(body), ";")
        )
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
                Value *$iv = $vtype__init__($i);
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
        out = tstr("Value *$name($args) {\n$body\n}")

        body = self.compile(node.body)
        out["body"] = (
            strip_parens(str(body), "{")
            if isinstance(self.unlink(node.body), Block)
            else "return " + ensuresuffix(str(body), ";")
        )
        out["name"] = self.compile(node.name)
        out["args"] = ", ".join(
            f"Value *{self.compile(self.unlink(arg).name)}"  # type: ignore
            for arg in node.params
        )
        return out

    def identifier_(self, node: Identifier, link: int) -> tstr:
        prefix = (
            ""
            if node.name in self.env.externs
            and self.env.externs[node.name]["type"] == "macro"
            else self._imported_names.get(node.name, f"und_{self.uid}_")
        )
        return tstr(prefix + node.name, meta={"reference": True})

    def if_(self, node: If, link: int) -> tstr:
        if node.expression:
            out = tstr("(__cbool__($condition) ? ($then) : ($else))")
        else:
            out = tstr("if (__cbool__($condition)) { $then }") + (
                tstr("else { $else }") if node.else_branch else ""
            )

        out["condition"] = self.compile(node.condition)
        out["then"] = self.compile(node.then_branch)
        out["else"] = self.compile(node.else_branch) if node.else_branch else ""

        if not node.expression:
            out["then"] = ensuresuffix(str(out["then"]), ";")  # type: ignore
            out["else"] = ensuresuffix(str(out["else"]), ";")  # type: ignore

        return out

    def index_(self, node: Index, link: int) -> tstr:
        if self._link2type(node.index) == "slice":
            return self.slice_(node, link)

        if (iterable_type := self._link2type(node.iterable)) != "any":
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
        out = tstr("$type__init__($value)") if init else tstr("$value")

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

        out["type"] = typ
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

    def variable_(self, node: Variable, link: int) -> tstr:
        out = tstr("$name = $value")
        addr = node.meta["address"]

        out["name"] = self.compile(node.name)
        out["value"] = self.compile(node.value)

        if addr not in self._defined_addrs:
            self._defined_addrs.add(addr)
            out = tstr("Value *") + out

        return out

    def variable_declaration_(self, node: Variable, link: int) -> tstr:
        out = tstr("Value *$name")

        out["name"] = self.compile(node.name)

        self._defined_addrs.add(node.meta["address"])

        return out

    def while_loop_(self, node: WhileLoop, link: int) -> tstr:
        out = tstr("while (__cbool__($condition)) { $body }")

        out["condition_type"] = str(self._link2type(node.condition))
        out["condition"] = self.compile(node.condition)
        body = self.compile(node.body)
        out["body"] = (
            strip_parens(str(body), "{")
            if isinstance(self.unlink(node.body), Block)
            else ensuresuffix(str(body), ";")
        )

        return out

    def unlink(self, link: int | Link | Any):
        if isinstance(link, (int, Link)):
            target = link if isinstance(link, int) else link.target
            return self.env.nodes[target]
        return link

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
        self._builtins()

        code = []
        for link in self.program:
            if stmt := str(self.compile(link)):
                code.append(stmt + ";")

        code = "\n".join(code).strip()

        return CompiledModule(
            meta=self.module,
            imports=self.imports,
            include=self.include,
            code=code,
        )

    def process_header(self):
        for i, node in enumerate(self.header.imports):
            if isinstance(node, FromImport):
                uid = md5(self.imports[i].encode()).hexdigest()[:8]
                if node.names is None:
                    # import *
                    names = list(self.env.imports[node.module.name].names.keys())
                    self._imported_names.update({name: f"und_{uid}_" for name in names})
                else:
                    # import a, b, c
                    self._imported_names.update(
                        {name.name: f"und_{uid}_" for name in node.names}
                    )

    def _builtins(self):
        uid = md5("stdlib/builtins.und".encode()).hexdigest()[:8]
        names = ["echo", "input", "random", "floor"]
        self._imported_names.update({name: f"und_{uid}_" for name in names})

    def _node2type(self, node) -> T:
        return self.env.names[node.meta["address"]]

    def _link2type(self, link: int | Link | Any) -> str:
        link = link.target if isinstance(link, Link) else link
        if not isinstance(link, int):
            raise TypeError(f"Expected int, got {type(link).__name__}")
        return self.env.typed[link]
