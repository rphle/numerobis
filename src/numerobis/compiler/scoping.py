"""Variable scoping and closure analysis for function definitions."""

import dataclasses
from typing import Any

from numerobis.nodes.unit import Expression

from ..nodes.ast import ForLoop, Function, ModuleAccess, Variable, VariableDeclaration
from ..nodes.core import AstNode, Identifier
from ..typechecker.linking import Link
from ..typechecker.linking import unlink as _unlink


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
                if (
                    "address" in n.meta
                    and n.meta["address"] in defined_addrs
                    and var_name not in current_defined
                ):
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
            case ModuleAccess():
                mod = table[n.module.target].name  # type: ignore
                name = f"{mod}.{table[n.name.target].name}"  # type: ignore
                if name not in current_defined:
                    used.add(name)
                return
            case Expression():
                return

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
