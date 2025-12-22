import subprocess
from functools import lru_cache
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
    Integer,
    String,
    UnaryOp,
    Variable,
)
from nodes.core import Identifier
from typechecker.linking import Link
from typechecker.types import BoolType, NumberType, StrType
from utils import camel2snake_pattern

from . import gcc as gnucc
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

        self.include = set({"unidad/runtime"})
        self._defined_addrs = set()

    def bin_op_(self, node: BinOp, link: int) -> str:
        out = tstr("$left $op $right")

        out["left"] = self.compile(node.left)
        out["right"] = self.compile(node.right)

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

        return str(out)

    def block_(self, node: Block, link: int) -> str:
        out = []

        for stmt in node.body:
            out.append(self.compile(stmt) + ";")

        return "\n".join(out)

    def boolean_(self, node: Boolean, link: int) -> str:
        self.include.add("stdbool")
        return ["false", "true"][node.value]

    def bool_op_(self, node: BoolOp, link: int) -> str:
        out = tstr("$left $op $right")

        out["left"] = self.compile(node.left)
        out["right"] = self.compile(node.right)
        out["op"] = {"and": "&&", "or": "||", "xor": "^"}[node.op.name]

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
        op_map = {
            "lt": "<",
            "le": "<=",
            "gt": ">",
            "ge": ">=",
            "eq": "==",
            "ne": "!=",
        }

        values = [self.compile(node.left)] + [self.compile(c) for c in node.comparators]

        comparisons = [
            f"({values[i]} {op_map[self.unlink(op).name]} {values[i + 1]})"  # type: ignore
            for i, op in enumerate(node.ops)
        ]

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

    def number_(self, node: Integer | Float) -> str:
        value = node.value
        if not node.exponent:
            return str(value)
        else:
            return f"{value}E{node.exponent}"

    def string_(self, node: String, link: int) -> str:
        return f"g_string_new({node.value})"

    def variable_(self, node: Variable, link: int) -> str:
        out = tstr("$type $name = $value")
        addr = self._link2addr(link)

        out["name"] = self.compile(node.name)
        out["type"] = self.typelink(link)
        out["value"] = self.compile(node.value)

        if out["type"] == "GString":
            out["name"] = f"*{out['name']}"

        if addr in self._defined_addrs:
            out.remove("type")
            out.strip()
        else:
            self._defined_addrs.add(addr)

        return str(out)

    def unary_op_(self, node: UnaryOp, link: int) -> str:
        out = tstr("$op($value)")

        out["op"] = {"not": "!", "sub": "-"}[node.op.name]
        out["value"] = self.compile(node.operand)

        return str(out)

    def variable_declaration_(self, node: Variable, link: int) -> str:
        out = tstr("$type $name")

        out["name"] = self.compile(node.name)
        out["type"] = self.typelink(link)

        self._defined_addrs.add(self._link2addr(link))

        return str(out)

    def typelink(self, link: int) -> str:
        value = self.env.names[self._link2addr(link)]

        match value:
            case NumberType():
                return "long" if value.typ == "Int" else "double"
            case StrType():
                return "GString"
            case BoolType():
                self.include.add("stdbool")
                return "bool"

        raise ValueError(f"Unknown type {value}")

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
            gnucc.compile(self.code)
            print(gnucc.run().stdout)
        except subprocess.CalledProcessError as e:
            self.errors.throw(901, command=" ".join(map(str, e.cmd)), help=e.stderr)

    @lru_cache(maxsize=None)
    def _link2addr(self, link: int) -> str:
        return self.env.typed[link]
