import dataclasses
from typing import Optional, TypeVar

from astnodes import AstNode, CallArg, FunctionAnnotation, Identifier, Operator, Unit

T = TypeVar("T", bound=AstNode)


@dataclasses.dataclass(frozen=True)
class Link(AstNode):
    target: int


def _link(node: AstNode) -> tuple[Link, dict[int, AstNode]]:
    table: dict[int, AstNode] = {}
    fields: dict[str, Link | list[Link]] = {}

    for field in dataclasses.fields(node):
        value = getattr(node, field.name)
        if isinstance(value, AstNode) and not isinstance(
            value, (Unit, Identifier, Operator, CallArg, FunctionAnnotation)
        ):
            this, linked = _link(value)
            table.update(linked)
            fields[field.name] = this
        elif isinstance(value, list):
            fields[field.name] = []
            for item in value:
                this, linked = _link(item)
                table.update(linked)
                fields[field.name].append(this)  # type: ignore

    cropped = dataclasses.replace(
        node,
        **{
            field: target if not isinstance(target, list) else tuple(target)
            for field, target in fields.items()
        },
    )
    hashed = cropped.hash()
    table[hashed] = cropped

    return Link(hashed), table


def link(tree: list[AstNode]) -> tuple[list[Link], dict[int, AstNode]]:
    table = {}
    fields = []

    for node in tree:
        this, linked = _link(node)
        table.update(linked)
        fields.append(this)

    return fields, table


def unlink(
    table: dict[int, AstNode], node: T, attrs: Optional[tuple | list] = None
) -> T:
    if isinstance(node, Link):
        return table[node.target]  # type: ignore

    try:
        dataclasses.fields(node)
    except TypeError:
        return node

    fields = {}
    for field in dataclasses.fields(node):
        if attrs is not None and field.name not in attrs:
            continue
        value = getattr(node, field.name)
        if isinstance(value, Link):
            fields[field.name] = table[value.target]
        elif isinstance(value, tuple):
            fields[field.name] = []
            for item in value:
                if isinstance(item, Link):
                    fields[field.name].append(table[item.target])
                else:
                    fields[field.name].append(item)

    unlinked = dataclasses.replace(
        node,
        **{field: target for field, target in fields.items()},
    )

    return unlinked
