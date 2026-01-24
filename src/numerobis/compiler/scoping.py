import dataclasses
from typing import Any

from nodes.ast import ForLoop, Function, Variable, VariableDeclaration
from nodes.core import AstNode, Identifier
from typechecker.linking import Link
from typechecker.linking import unlink as _unlink


def get_free_vars(
    table: dict[int, AstNode], node: Function, link: int, defined_addrs: dict[str, str]
) -> list[str]:
    """
    Finds identifiers used in a node that are not defined within that node's scope.
    """
    unlink = lambda x: _unlink(table, x)  # noqa: E731

    used = set()
    defined = {unlink(unlink(p).name).name for p in node.params}
    if node.name:
        defined.add(unlink(node.name).name)

    def visit(n: Any, current_defined: set):
        if isinstance(n, Link):
            n = table[n.target]

        try:
            fields = dataclasses.fields(n)
        except TypeError:
            return

        match n:
            case Identifier():
                if n.name not in current_defined:
                    used.add(n.name)
                return
            case Variable() | VariableDeclaration():
                var_name = unlink(n.name).name
                if n.meta["address"] in defined_addrs:
                    used.add(defined_addrs[n.meta["address"]])
                    return
                current_defined.add(var_name)
            case Function():
                if n.name is not None:
                    var_name = unlink(n.name).name
                    current_defined.add(var_name)
                for param in n.params:
                    current_defined.add(unlink(unlink(param).name).name)
            case ForLoop():
                for iterator in n.iterators:
                    current_defined.add(unlink(iterator).name)

        for field in fields:
            if field.name in ("name", "annotation", "unit"):
                continue

            val = getattr(n, field.name)
            if isinstance(val, (list, tuple)):
                for item in val:
                    visit(item, current_defined)
            elif val is not None:
                visit(val, current_defined)

    visit(node.body, defined)

    return sorted(list(used))
