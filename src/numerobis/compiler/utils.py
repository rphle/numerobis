import hashlib
from functools import lru_cache
from hashlib import md5
from pathlib import Path
from typing import Literal

from ..nodes.core import Identifier, UnitNode
from ..nodes.unit import Call, Expression, Neg, Power, Product, Scalar, Sum

BUILTINS = [
    "echo",
    "input",
    "exit",
    "Str.len",
    "Str.split",
    "List.len",
    "List.append",
    "List.extend",
    "List.pop",
    "List.insert",
    "List.indexof",
    "List.contains",
    "cli_args",
]


def ensuresuffix(s: str, ch: str) -> str:
    return s if s.endswith(ch) else s + ch


def mthd(name, *args):
    return f"NUMEROBIS_METHODS[{args[0]}.type]->{name}({', '.join(args)})"


def repr_double(s):
    single = "'" + repr('"' + s)[2:]
    return '"' + single[1:-1].replace('"', '\\"').replace("\\'", "'") + '"'


def strip_parens(s: str, char: Literal["(", "[", "{"]) -> str:
    s = s.strip()
    rchar = {"(": ")", "[": "]", "{": "}"}
    if s.startswith(char) and s.endswith(rchar[char]):
        s = s[1:-1]
    return s


def mangle(name: str) -> str:
    return name.replace("_", "__").replace(".", "_d")


def compile_math(node: UnitNode) -> str:
    match node:
        case Expression():
            return compile_math(node.value)
        case Sum() | Product():
            op = "+" if isinstance(node, Sum) else "*"
            return "(" + op.join(compile_math(v) for v in node.values) + ")"
        case Power():
            return f"pow({compile_math(node.base)}, {compile_math(node.exponent)})"
        case Scalar():
            return str(node.value)
        case Call():
            return f"{compile_math(node.callee)}({','.join(compile_math(a.value) for a in node.args)})"
        case Identifier():
            return node.name
        case Neg():
            return "-(" + compile_math(node.value) + ")"
        case _:
            raise NotImplementedError(f"Unit node cannot be compiled: {type(node)}")


@lru_cache(maxsize=None)
def module_uid(path: str | Path) -> str:
    uid = md5(str(Path(path).resolve()).encode()).hexdigest()[:8]
    return str(uid)


@lru_cache(maxsize=None)
def unit_uid(n: str, uid: str) -> str:
    return "U" + hashlib.sha1((n + "_" + uid).encode("utf-8")).hexdigest()[:8].upper()
