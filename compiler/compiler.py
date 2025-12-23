import subprocess
from typing import Any

import typechecker.declare as declare
from classes import ModuleMeta
from compiler.utils import ensuresuffix
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
    If,
    Index,
    Integer,
    Slice,
    String,
    UnaryOp,
    Variable,
)
from nodes.core import Identifier
from typechecker.linking import Link
from typechecker.types import BoolType, NumberType, StrType, T
from utils import camel2snake_pattern

from . import gcc as gnucc
from .constants import SLICE_NONE
from .tstr import tstr


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

        self.include = set({"unidad/runtime", "unidad/constants"})
        self._defined_addrs = set()

    def bin_op_(self, node: BinOp, link: int) -> str:
        operands = [self.compile(node.left), self.compile(node.right)]
        if "function" not in node.meta:
            # two numbers
            out = tstr("$left $op $right")
            out["left"], out["right"] = operands

            match node.op.name:
                case "pow":
                    self.include.add("math")
                    return f"pow({out['left']}, {out['right']})"
                case "mod":
                    self.include.add("math")
                    return f"fmod({out['left']}, {out['right']})"
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
            out = tstr("$func($left, $right)")
            reverse = node.meta["function"][0] == "right"
            out["left"], out["right"] = operands if not reverse else operands[::-1]
            out["func"] = node.meta["function"][1]

        return str(out)

    def block_(self, node: Block, link: int) -> str:
        out = []

        for stmt in node.body:
            out.append(self.compile(stmt) + ";")

        return "\n".join(out)

    def boolean_(self, node: Boolean, link: int) -> str:
        self.include.add("stdbool")
        self.include.add("unidad/types/bool")
        return ["false", "true"][node.value]

    def bool_op_(self, node: BoolOp, link: int) -> str:
        out = tstr("$lfunc($left) $op $rfunc($right)")
        self.include.add("unidad/types/bool")

        out["left"] = self.compile(node.left)
        out["right"] = self.compile(node.right)
        out["op"] = {"and": "&&", "or": "||", "xor": "^"}[node.op.name]

        out["lfunc"] = f"{self._link2type(node.left)}__bool__"
        out["rfunc"] = f"{self._link2type(node.right)}__bool__"

        return str(out)

    def call_(self, node: Call, link: int) -> str:
        out = tstr("$callee($args)")

        out["callee"] = self.compile(node.callee)
        out["args"] = ", ".join(
            self.compile(self.unlink(arg).value)  # type: ignore
            for arg in node.args
        )

        return str(out)

    def compare_(self, node: Compare, link: int) -> str:
        comparators = [node.left, *node.comparators]
        values = [self.compile(c) for c in comparators]

        comparisons = []
        for i, op in enumerate(node.ops):
            opname = self.unlink(op).name  # type: ignore
            if (
                opname in ["eq", "ne"]
                and node.meta["functions"][i][2][0] != node.meta["functions"][i][2][1]
            ):
                return "false" if opname == "eq" else "true"

            out = tstr("$func($left, $right)")
            reverse = node.meta["functions"][i][0] == "right"
            operands = [values[i], values[i + 1]]

            out["left"], out["right"] = operands if not reverse else operands[::-1]
            out["func"] = (
                node.meta["functions"][i][1]
                if opname != "ne"
                else f"!{node.meta['functions'][i][1].replace('__ne', '__eq')}"  # auto-delegate !=
            )

            comparisons.append(str(out))

        return "(" + " && ".join(comparisons) + ")"

    def identifier_(self, node: Identifier, link: int) -> str:
        if node.name in declare.names:
            self.include.add("unidad/" + node.name)  # e.g. echo or input
        return node.name

    def if_(self, node: If, link: int) -> str:
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
            out["then"] = ensuresuffix(out["then"], ";")  # type: ignore
            out["else"] = ensuresuffix(out["else"], ";")  # type: ignore

        return str(out)

    def index_(self, node: Index, link: int) -> str:
        if self._link2type(node.index) == "slice":
            return self.slice_(node, link)

        out = tstr("$func($this, $index)")

        out["func"] = f"{self._link2type(link)}__getitem__"
        out["this"] = self.compile(node.iterable)
        out["index"] = self.compile(node.index)

        self.include.add(f"unidad/types/{self._link2type(link)}")

        return str(out)

    def number_(self, node: Integer | Float) -> str:
        self.include.add("unidad/types/number")
        value = node.value
        if not node.exponent:
            return str(value)
        else:
            return f"{value}E{node.exponent}"

    def slice_(self, node: Index, link: int) -> str:
        index = self.unlink(node.index)
        assert isinstance(index, Slice)
        out = tstr("$func($this, $start, $stop, $step)")

        out["func"] = f"{self._link2type(link)}__getslice__"
        out["this"] = self.compile(node.iterable)
        out["start"] = (
            self.compile(index.start) if index.start is not None else SLICE_NONE
        )
        out["stop"] = self.compile(index.stop) if index.stop is not None else SLICE_NONE
        out["step"] = self.compile(index.step) if index.step is not None else SLICE_NONE

        self.include.add(f"unidad/types/{self._link2type(link)}")

        return str(out)

    def string_(self, node: String, link: int) -> str:
        self.include.add("unidad/types/str")
        return f"g_string_new({node.value})"

    def variable_(self, node: Variable, link: int) -> str:
        out = tstr("$type $name = $value")
        addr = node.meta["address"]

        out["name"] = self.compile(node.name)
        out["type"] = self.type_(self._node2type(node))
        out["value"] = self.compile(node.value)

        if addr in self._defined_addrs:
            out.remove("type")
            out.strip()
        else:
            self._defined_addrs.add(addr)
            if out["type"] == "GString":
                out["name"] = f"*{out['name']}"

        return str(out)

    def unary_op_(self, node: UnaryOp, link: int) -> str:
        out = tstr("$op($value)")
        self.include.add("unidad/types/bool")

        out["op"] = {"not": f"!{self._link2type(node.operand)}__bool__", "sub": "-"}[
            node.op.name
        ]
        out["value"] = self.compile(node.operand)

        return str(out)

    def variable_declaration_(self, node: Variable, link: int) -> str:
        out = tstr("$type $name")

        out["name"] = self.compile(node.name)
        out["type"] = self.type_(self._node2type(node))

        self._defined_addrs.add(node.meta["address"])

        return str(out)

    def type_(self, node: T | Any) -> str:
        match node:
            case NumberType():
                return "long" if node.typ == "Int" else "double"
            case StrType():
                return "GString"
            case BoolType():
                self.include.add("stdbool")
                return "bool"

        raise ValueError(f"Unknown type {node}")

    def unlink(self, link: int | Link | Any):
        if isinstance(link, (int, Link)):
            target = link if isinstance(link, int) else link.target
            return self.env.nodes[target]
        return link

    def compile(self, link: Link | Any) -> str:
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
            output.append(self.compile(link) + ";")

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
