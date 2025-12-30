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
from .utils import _getitem_, ensuresuffix, star


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
            }
        )
        self._defined_addrs = set()

    def bin_op_(self, node: BinOp, link: int) -> tstr:
        operands = [self.compile(node.left), self.compile(node.right)]
        if "side" not in node.meta:
            # two numbers
            out = tstr("$left $op $right")
            out["left"], out["right"] = operands

            match node.op.name:
                case "pow":
                    self.include.add("math")
                    return tstr(f"pow({out['left']}, {out['right']})")
                case "mod":
                    self.include.add("math")
                    return tstr(f"fmod({out['left']}, {out['right']})")
                case _:
                    out["op"] = {
                        "add": "+",
                        "sub": "-",
                        "mul": "*",
                        "div": "/",
                        "pow": "^",
                        "intdiv": "//",
                    }[node.op.name]
        else:
            out = tstr("__$func__($left, $right)")
            out["left"], out["right"] = operands[:: node.meta["side"]]
            out["func"] = node.op.name

        return out

    def block_(self, node: Block, link: int) -> tstr:
        out = []

        for stmt in node.body:
            out.append(str(self.compile(stmt)) + ";")

        return tstr("\n".join(out))

    def boolean_(self, node: Boolean, link: int) -> tstr:
        self.include.add("stdbool")
        self.include.add("unidad/types/bool")
        return tstr(f"bool__init__({['false', 'true'][node.value]})")

    def bool_op_(self, node: BoolOp, link: int) -> tstr:
        out = tstr("$lfunc($left) $op $rfunc($right)")
        self.include.add("unidad/types/bool")

        out["left"] = self.compile(node.left)
        out["right"] = self.compile(node.right)
        out["op"] = {"and": "&&", "or": "||", "xor": "^"}[node.op.name]

        out["lfunc"] = f"{self._link2type(node.left)}__bool__"
        out["rfunc"] = f"{self._link2type(node.right)}__bool__"

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
        self.include.add("unidad/types/bool")

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
                comparisons.append("!" + str(out))
            else:
                comparisons.append(str(out))

        return tstr("(" + " && ".join(comparisons) + ")")

    def for_loop_(self, node: ForLoop, link: int) -> tstr:
        if self._link2type(node.iterable) == "range":
            return self.for_loop_range_(node, link)

        if "value" not in node.meta:
            return tstr("// empty loop")

        loop = tstr("""for (size_t $iterator = 0; $iterator < $iterable_type_len($iterable); $iterator++) {
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
        iterator_type = str(self.type_(node.meta["value"]))
        iterator_name = f"__iterator_{abs(link)}"
        iterable_name = f"__iterable_{abs(link)}"
        loop["iterator"], loop["iterable"] = iterator_name, iterable_name
        loop["iterable_type"] = iterable_type

        iterators = [self.unlink(iterator) for iterator in node.iterators]

        if len(node.iterators) == 1:
            iterator = iterators[0]
            loop["iterator_defs"] = (
                f"{iterator_type} {star(iterator_type)}{iterator.name} = "  # type: ignore
                + _getitem_("$iterator", "$iterable", iterator_type, iterable_type)
                + ";"
            )
        else:
            # if there are >1 iterators, it is guaranteed that the iterable is a list of lists
            iterrow_name = f"__iterrow_{abs(link)}"
            iterator_defs = (
                f"GArray *{iterrow_name} = UNBOX(GArray *, list__getitem__($iterable, $iterator));"
                + "\n".join(
                    f"{iterator_type} {star(iterator_type)}{iterator.name} = "  # type: ignore
                    + _getitem_(str(i), iterrow_name, iterator_type, iterable_type)
                    + ";"
                    for i, iterator in enumerate(iterators)
                )
            )
            loop["iterator_defs"] = iterator_defs

        iterable = self.compile(node.iterable)
        if "reference" not in iterable.meta:
            out = tstr("{\n$iterable_def;\n$loop}")
            out["iterable_def"] = (
                f"{self.type_(loop['iterable_type'])} {star(str(loop['iterable_type']))}{iterable_name} = {iterable}"
            )
            out["loop"] = loop
            return out
        else:
            loop["iterable"] = iterable

        return loop

    def for_loop_range_(self, node: ForLoop, link: int) -> tstr:
        loop = tstr("""for (gint64 $i = $range.start;
                           ($range.step > 0) ? ($i < $range.stop) : ($i > $range.stop);
                           $i += $range.step)
                       {$body}""")

        body = self.compile(node.body)
        loop["body"] = (
            str(body).lstrip("{").rstrip("}")
            if isinstance(node.body, Block)
            else ensuresuffix(str(body), ";")
        )
        loop["i"] = self.compile(node.iterators[0])

        range_ = self.compile(node.iterable)

        if "reference" not in range_.meta:
            out = tstr("{\n$range_def;\n$loop}")
            name = f"__range_{abs(link)}"
            out["range_def"] = f"Range {name} = {range_}"
            loop["range"] = name
            out["loop"] = loop
            return out

        loop["range"] = range_

        return loop

    def identifier_(self, node: Identifier, link: int) -> tstr:
        if node.name in declare.names:
            self.include.add("unidad/" + node.name)  # e.g. echo or input
        return tstr(node.name, meta={"reference": True})

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

        out = tstr("__getitem__($iterable, $index)")
        out["index"] = str(self.compile(node.index))
        out["iterable"] = str(self.compile(node.iterable))

        return out

    def list_(self, node: List, link: int) -> tstr:
        self.include.add("unidad/types/list")
        out = tstr("list_of($items)")

        out["items"] = ", ".join(
            [f"BOX({self.compile(item)})" for item in node.items] + ["NULL"]
        )

        return out

    def number_(self, node: Integer | Float) -> tstr:
        self.include.add("unidad/types/number")
        out = tstr("$type__init__($value)")

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
        return tstr(f"{{ .start = {start}, .stop = {stop}, .step = {step} }}")

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
        out = tstr("$op($value)")
        self.include.add("unidad/types/bool")

        out["op"] = {
            "not": f"!{self._link2type(node.operand)}__bool__",
            "sub": "__neg__",
        }[node.op.name]
        out["value"] = self.compile(node.operand)

        return out

    def variable_(self, node: Variable, link: int) -> tstr:
        out = tstr("*$name = $value")
        addr = node.meta["address"]

        out["name"] = self.compile(node.name)
        out["type"] = str(self.type_(self._node2type(node)))
        out["value"] = self.compile(node.value)

        if addr not in self._defined_addrs:
            self._defined_addrs.add(addr)
            out = tstr("Value ") + out

        return out

    def variable_declaration_(self, node: Variable, link: int) -> tstr:
        out = tstr("$type $name")

        out["name"] = self.compile(node.name)
        out["type"] = self.type_(self._node2type(node))

        self._defined_addrs.add(node.meta["address"])

        return out

    def while_loop_(self, node: WhileLoop, link: int) -> tstr:
        out = tstr("while ($condition_type__bool__($condition)) { $body }")

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

    def start(self):
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

        code = subprocess.run(
            ["clang-format"], input=code, text=True, capture_output=True
        ).stdout

        print(code)
        self.code = code
        return code

    def gcc(self):
        try:
            gnucc.compile(self.code, include=list(self.include))
            print(gnucc.run().stdout)
        except subprocess.CalledProcessError as e:
            self.errors.throw(901, command=" ".join(map(str, e.cmd)), help=e.stderr)

    def _node2type(self, node) -> T:
        return self.env.names[node.meta["address"]]

    def _link2type(self, link: int | Link | Any) -> str:
        link = link.target if isinstance(link, Link) else link
        if not isinstance(link, int):
            raise TypeError(f"Expected int, got {type(link).__name__}")
        return self.env.typed[link]
