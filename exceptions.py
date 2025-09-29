import sys

import rich.console
import rich.markup

from astnodes import AstNode, BinOp, Location, Token
from classes import ModuleMeta


class uException:
    def __init__(
        self,
        message,
        module: ModuleMeta,
        help: str | None = None,
        loc: Location | None = None,
    ):
        if isinstance(loc, (AstNode, Token)):
            loc = loc.loc
        console = rich.console.Console()
        console.print(
            rf'[reset][dim]\[at "{module.path if module.path else "<unknown>"}"'
            + (f", line {loc.line}, col {loc.col}]" if loc else "]")
            + "[/dim]",
            # highlight=False,
        )
        console.print(
            f"[red][bold]{self.__class__.__name__.removeprefix('u').replace('_', ' ')}[/bold]: {message}[/red]",
            highlight=False,
        )
        if help:
            console.print(
                f"[bold]help:[/bold] {rich.markup.escape(help)}",
                highlight=False,
            )
        sys.exit(1)


class uError(uException):
    pass


class uSyntaxError(uException):
    pass


class uNameError(uException):
    pass


class Dimension_Mismatch(uException):
    pass


class Exceptions:
    def __init__(self, module: ModuleMeta):
        self.module = module

    def unexpectedToken(
        self,
        tok: Token,
        help: str | None = None,
        loc: Location | None = None,
    ):
        uSyntaxError(
            f"Unexpected token: '{tok.value}'",
            module=self.module,
            help=help,
            loc=loc or tok.loc,
        )

    def unexpectedEOF(self, loc: Location | None = None):
        uSyntaxError(
            "Unexpected EOF",
            module=self.module,
            loc=loc,
        )

    def binOpMismatch(self, node: BinOp, data: list[dict]):
        names = {
            "plus": "addition",
            "minus": "subtraction",
            "times": "multiplication",
            "divide": "division",
        }
        Dimension_Mismatch(
            f"incompatible dimensions in {names[node.op.name]} {data[0]['dim']} to {data[1]['dim']}",
            module=self.module,
            loc=node.loc,
        )

    def throw(
        self,
        exception: type[uException],
        message: str,
        help: str | None = None,
        loc: Location | None = None,
    ):
        exception(message=message, module=self.module, help=help, loc=loc)
