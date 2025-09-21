import sys

import rich

from astnodes import AstNode
from classes import Location, Token


class uException:
    def __init__(
        self, message, path: str = None, loc: AstNode | Token | Location = None
    ):
        if isinstance(loc, (AstNode, Token)):
            loc = loc.loc
        console = rich.console.Console()
        console.print(
            f'[reset][dim]\[at "{path if path else "<unknown>"}"'
            + (f", line {loc.line}, column {loc.col}]" if loc else "]")
            + "[/dim]",
            # highlight=False,
        )
        console.print(
            f"[red][bold]{self.__class__.__name__.removeprefix('u')}[/bold]: {message}[/red]",
            highlight=False,
        )
        sys.exit(1)


class uSyntaxError(uException):
    pass
