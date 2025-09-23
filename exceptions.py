import sys

import rich
import rich.markup

from astnodes import AstNode
from classes import Location, Token


class uException:
    def __init__(
        self,
        message,
        help: str | None = None,
        path: str | None = None,
        loc: AstNode | Token | Location | None = None,
    ):
        if isinstance(loc, (AstNode, Token)):
            loc = loc.loc
        console = rich.console.Console()
        console.print(
            rf'[reset][dim]\[at "{path if path else "<unknown>"}"'
            + (f", line {loc.line}, column {loc.col}]" if loc else "]")
            + "[/dim]",
            # highlight=False,
        )
        console.print(
            f"[red][bold]{self.__class__.__name__.removeprefix('u')}[/bold]: {message}[/red]",
            highlight=False,
        )
        if help:
            console.print(
                f"[bold]help:[/bold] {rich.markup.escape(help)}",
                highlight=False,
            )
        sys.exit(1)


class uSyntaxError(uException):
    pass


class Exceptions:
    def __init__(self, path: str | None):
        self.path = path

    def unexpectedToken(
        self,
        tok: Token,
        help: str | None = None,
        loc: Location | None = None,
    ):
        uSyntaxError(
            f"Unexpected token: '{tok.value}'",
            path=self.path,
            help=help,
            loc=loc or tok.loc,
        )

    def unexpectedEOF(self, loc: Location | None = None):
        uSyntaxError(
            "Unexpected EOF",
            path=self.path,
            loc=loc,
        )

    def throw(
        self,
        exception: type[uException],
        message: str,
        help: str | None = None,
        loc: Location | None = None,
    ):
        exception(message=message, help=help, path=self.path, loc=loc)
