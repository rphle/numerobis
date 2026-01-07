import dataclasses
from typing import Any

from nodes.ast import Function, Variable, VariableDeclaration
from nodes.core import AstNode, Identifier
from typechecker.linking import Link, unlink

from .utils import BUILTINS


def get_free_vars(table: dict[int, AstNode], node: Function, link: int) -> list[str]:
    """
    Finds identifiers used in a node that are not defined within that node's scope.
    """
    used = set()
    defined = {unlink(table, unlink(table, p).name).name for p in node.params}
    if node.name:
        defined.add(unlink(table, node.name).name)

    def visit(n: Any, current_defined: set):
        if isinstance(n, Link):
            n = table[n.target]

        try:
            fields = dataclasses.fields(n)
        except TypeError:
            return

        match n:
            case Identifier():
                if (n.name not in current_defined and n.name not in BUILTINS) or (
                    n.meta.get("link") == link
                ):
                    used.add(n.name)
                return
            case Variable() | VariableDeclaration():
                var_name = unlink(table, n.name).name
                current_defined.add(var_name)
            case Function():
                if n.name is not None:
                    var_name = unlink(table, n.name).name
                    current_defined.add(var_name)

        for field in fields:
            if field.name in ("name", "annotation"):
                continue

            val = getattr(n, field.name)
            if isinstance(val, (list, tuple)):
                for item in val:
                    visit(item, current_defined)
            elif val is not None:
                visit(val, current_defined)

    visit(node.body, defined)

    return sorted(list(used))
