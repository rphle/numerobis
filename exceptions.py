import sys

import rich.console
import rich.markup

from astnodes import BinOp, Location, Token
from classes import ModuleMeta


class uException:
    def __init__(
        self,
        message,
        module: ModuleMeta,
        help: str | None = None,
        preview: bool = True,
        loc: Location | None = None,
        exit: bool = True,
    ):
        console = rich.console.Console()
        console.print(
            rf'[reset][dim]\[at "{module.path if module.path else "<unknown>"}"'
            + (f", line {loc.line}, col {loc.col}]" if loc else "]")
            + "[/dim]",
            highlight=False,
        )

        if (
            preview
            and loc is not None
            and module.source
            and 0 < loc.end_line <= len(module.source.splitlines())
        ):
            for line in loc.split():
                line.end_line = (
                    line.end_line
                    if line.end_line > 0
                    else len(module.source.splitlines())
                )
                line.end_col = (
                    line.end_col
                    if line.end_col > 0
                    else len(module.source.splitlines()[line.line - 1]) + 1
                )

                src = module.source.splitlines()[line.line - 1]
                start = max(0, line.col - 30)
                end = min(len(src), line.end_col + 30)

                highlighted = (
                    f"{rich.markup.escape(src[start : line.col - 1])}"
                    f"[red]{rich.markup.escape(src[line.col - 1 : line.end_col])}[/red]"
                    f"{rich.markup.escape(src[line.end_col : end])}"
                )
                prefix = "..." if start > 0 else ""
                suffix = "..." if end < len(src) else ""

                console.print(
                    f"[dim]{line.line}|[/dim]   {prefix}{highlighted}{suffix}\n"
                    f"{' ' * len(f'{line.line}|   {prefix}{src[start : line.col - 1]}')}[red bold]{'^' * (line.end_col - line.col + 1)}[/bold red]",
                    highlight=False,
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
        if exit:
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
    ):
        uSyntaxError(
            f"Unexpected token: '{tok.value}'",
            module=self.module,
            help=help,
            loc=tok.loc,
        )

    def unexpectedEOF(self, loc: Location | None = None):
        uSyntaxError(
            "Unexpected EOF",
            module=self.module,
            loc=loc,
        )

    def binOpMismatch(self, node: BinOp, texts: list[str]):
        names = {
            "plus": "addition",
            "minus": "subtraction",
            "times": "multiplication",
            "divide": "division",
        }
        Dimension_Mismatch(
            f"incompatible dimensions in {names[node.op.name]}",
            module=self.module,
            loc=node.loc,
            exit=False,
        )

        print("   left hand side:", texts[0])
        print("  right hand side:", texts[1])

        sys.exit(1)

    def throw(
        self,
        exception: type[uException],
        message: str,
        help: str | None = None,
        loc: Location | None = None,
    ):
        exception(message=message, module=self.module, help=help, loc=loc)
