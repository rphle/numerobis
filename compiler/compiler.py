import dataclasses
import re
import subprocess
from typing import Any

import typechecker.declare as declare
from classes import ModuleMeta
from environment import Namespaces
from exceptions.exceptions import Exceptions
from nodes.ast import (
    BinOp,
    Block,
    Boolean,
    BoolOp,
    Call,
    Compare,
    Float,
    ForLoop,
    If,
    Index,
    Integer,
    List,
    Range,
    Slice,
    String,
    UnaryOp,
    Variable,
    WhileLoop,
)
from nodes.core import Identifier
from typechecker.linking import Link
from typechecker.types import BoolType, ListType, NumberType, RangeType, StrType, T
from utils import camel2snake_pattern

from . import gcc as gnucc
from .tstr import tstr
from .utils import ensuresuffix, mthd, repr_double


class Compiler:
    def __init__(
        self,
        program: list[Link],
        module: ModuleMeta,
        namespaces: Namespaces = Namespaces(),
    ):
        self.program = program
        self.module = module
        self.errors = Exceptions(module=module)
        self.env = namespaces

        self.include = set(
            {
                "unidad/runtime",
                "unidad/constants",
                "unidad/utils/utils",
                "unidad/values",
                "unidad/types/bool",
                "unidad/exceptions/throw",
            }
        )
        self._defined_addrs = set()

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
        out["args"] = ", ".join(
            str(self.compile(self.unlink(arg).value))  # type: ignore
            for arg in node.args
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
            str(body).lstrip("{").rstrip("}")
            if isinstance(node.body, Block)
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
                f"Value *und_{iterator.name} = "  # type: ignore
                + mthd("__getitem__", "$iterable", "int__init__($iterator)")
                + ";"
            )
        else:
            # if there are >1 iterators, it is guaranteed that the iterable is a list of lists
            iterrow_name = f"__iterrow_{abs(link)}"
            iterator_defs = f"Value *{iterrow_name} = {mthd('__getitem__', '$iterable', 'int__init__($iterator)')};"
            iterator_defs += "\n".join(
                f"Value *und_{iterator.name} = "  # type: ignore
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
            Value *$iv = $vtype__init__($range->start);
            for ($type $i = $range->start;
                (($range->step > 0) ? ($i < $range->stop) : ($i > $range->stop));
                $i += $range->step)
            {
                $update
                $body
            }}""")

        body = self.compile(node.body)
        loop["body"] = (
            str(body).lstrip("{").rstrip("}")
            if isinstance(node.body, Block)
            else ensuresuffix(str(body), ";")
        )
        loop["i"] = f"__iterator_{abs(link)}"
        loop["iv"] = self.compile(node.iterators[0])

        loop["vtype"] = node.meta["value"].name().lower()  # 'int' or 'float'
        loop["type"] = {"Int": "gint64", "Float": "gdouble"}[node.meta["value"].name()]

        loop["update"] = (
            f"$iv->number->{ {'Int': 'i64', 'Float': 'f64'}[node.meta['value'].name()] } = $i;"
        )

        r = self.unlink(node.iterable)
        if not isinstance(r, Range):
            loop["range_def"] = self.compile(node.iterable)
            loop["range"] = f"__range_{abs(link)}"
            return loop

        # inline range
        assert isinstance(r, Range)
        loop = tstr(
            """{
            Value *$iv = $vtype__init__($start);
            for ($type $i = $start;
                (($step > 0) ? ($i < $stop) : ($i > $stop));
                $i += $step)
            {
                $update
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

    def identifier_(self, node: Identifier, link: int) -> tstr:
        if node.name in declare.names:
            self.include.add("unidad/" + node.name)  # e.g. echo or input
            return tstr(node.name, meta={"reference": True})
        return tstr("und_" + node.name, meta={"reference": True})

    def if_(self, node: If, link: int) -> tstr:
        if node.expression:
            out = tstr("(($condition) ? ($then) : ($else))")
        else:
            out = tstr("if ($condition) { $then }") + (
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

        self.include.add(f"unidad/types/{self._link2type(node.iterable)}")

        out = tstr("__getitem__($iterable, $index, $loc)")
        out["index"] = str(self.compile(node.index))
        out["iterable"] = str(self.compile(node.iterable))

        loc = node.loc
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

    def slice_(self, node: Index, link: int) -> tstr:
        index = self.unlink(node.index)
        assert isinstance(index, Slice)
        out = tstr("__getslice__($this, $start, $stop, $step)")

        out["this"] = self.compile(node.iterable)
        out["start"] = self.compile(index.start) if index.start is not None else "NONE"
        out["stop"] = self.compile(index.stop) if index.stop is not None else "NONE"
        out["step"] = self.compile(index.step) if index.step is not None else "NONE"

        self.include.add(f"unidad/types/{self._link2type(link)}")

        return out

    def string_(self, node: String, link: int) -> tstr:
        self.include.add("unidad/types/str")
        self.include.add("unidad/types/number")  # str.c includes number.h
        return tstr(f"str__init__(g_string_new({node.value}))")

    def type_(self, node: T | Any) -> tstr:
        match node:
            case NumberType() | "number":
                return tstr("gint64" if node.typ == "Int" else "gdouble")
            case StrType() | "str":
                return tstr("GString")
            case ListType() | "list":
                return tstr("GArray")
            case BoolType() | "bool":
                self.include.add("stdbool")
                return tstr("bool")
            case RangeType() | "range":
                self.include.add("unidad/types/range")
                return tstr("Range")
            case "int" | "float":
                return tstr("gint64" if node == "int" else "gdouble")

        raise ValueError(f"Unknown type {node}")

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
        out["type"] = str(self.type_(self._node2type(node)))
        out["value"] = self.compile(node.value)

        if addr not in self._defined_addrs:
            self._defined_addrs.add(addr)
            out = tstr("Value *") + out

        return out

    def variable_declaration_(self, node: Variable, link: int) -> tstr:
        out = tstr("$type $name")

        out["name"] = self.compile(node.name)
        out["type"] = self.type_(self._node2type(node))

        self._defined_addrs.add(node.meta["address"])

        return out

    def while_loop_(self, node: WhileLoop, link: int) -> tstr:
        out = tstr("while (__cbool__($condition)) { $body }")

        out["condition_type"] = str(self._link2type(node.condition))
        out["condition"] = self.compile(node.condition)
        body = self.compile(node.body)
        out["body"] = (
            str(body).lstrip("{").rstrip("}")
            if isinstance(node.body, Block)
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

    def start(self, format: bool = False):
        output = []

        for link in self.program:
            output.append(str(self.compile(link)) + ";")

        code = tstr("""$include

            int main() {
                $output
                return 0;
            }""")

        code["include"] = "\n".join([f"#include <{lib}.h>" for lib in self.include])
        code["output"] = "\n".join(output)
        code = str(code).strip()

        if format:
            code = subprocess.run(
                ["clang-format"], input=code, text=True, capture_output=True
            ).stdout

        print(code)
        self.code = code
        return code

    def gcc(self, output_path: str = "output/output"):
        self._source_h()
        try:
            gnucc.compile(self.code, output=output_path)
        except subprocess.CalledProcessError as e:
            self.errors.throw(201, command=" ".join(map(str, e.cmd)), help=e.stderr)

    def _node2type(self, node) -> T:
        return self.env.names[node.meta["address"]]

    def _link2type(self, link: int | Link | Any) -> str:
        link = link.target if isinstance(link, Link) else link
        if not isinstance(link, int):
            raise TypeError(f"Expected int, got {type(link).__name__}")
        return self.env.typed[link]

    def _source_h(self, target="compiler/runtime/unidad/exceptions/source.c"):
        content = open(target, "r", encoding="utf-8").read()
        content = re.sub(
            r"<CONTENT>.*</CONTENT>",
            (
                f"<CONTENT> */\n{repr_double(str(self.module.path))},\n"
                f"{len(self.module.source.split('\n'))},\n"
                f"{{ {repr_double(self.module.source).replace('\\n', '", "')} }}\n/* </CONTENT>"
            ),
            content,
            flags=re.MULTILINE | re.DOTALL,
        )
        open(target, "w", encoding="utf-8").write(content)
