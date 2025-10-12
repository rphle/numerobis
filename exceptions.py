import sys

import rich.console
import rich.markup

from astnodes import BinOp, Identifier, Location, Token
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
        error_type = self.__class__.__name__.removeprefix("u").replace("_", " ")

        # Header
        console.print()
        location = f"{module.path or '<unknown>'}" + (
            f":{loc.line}:{loc.col}" if loc else ""
        )
        console.print(
            f"[bold red]{error_type}[/bold red] [dim]at {location}[/dim]",
            highlight=False,
        )
        console.print(f"  {message}", highlight=False)

        # Code preview
        source_lines = module.source.splitlines()
        if preview and loc and module.source and 0 < loc.end_line <= len(source_lines):
            console.print()

            locs = loc.split()
            for i, line in enumerate(locs):
                line.end_line = (
                    line.end_line if line.end_line > 0 else len(source_lines)
                )
                line.end_col = (
                    line.end_col
                    if line.end_col > 0
                    else len(source_lines[line.line - 1]) + 1
                )

                src = source_lines[line.line - 1]
                start = max(0, line.col - 30)
                end = min(len(src), line.end_col + 30)

                highlighted = (
                    f"{rich.markup.escape(src[start : line.col - 1])}"
                    f"[red bold]{rich.markup.escape(src[line.col - 1 : line.end_col])}[/red bold]"
                    f"{rich.markup.escape(src[line.end_col : end])}"
                )
                prefix = "..." if start > 0 else ""
                suffix = "..." if end < len(src) else ""

                console.print(
                    f"[dim]    {line.line} │[/dim]   {prefix}{highlighted}{suffix}",
                    highlight=False,
                )

                underline = "─" * (line.end_col - line.col + 1)
                if i == 0:
                    underline = "╰" + underline[1:]
                if i == len(locs) - 1:
                    underline = underline[:-1] + "╯"
                marker = f"{' ' * len(f'{prefix}{src[start : line.col - 1]}')}[red bold]{underline}[/bold red]"

                console.print(
                    f"[dim]    {' ' * len(str(line.line))} │[/dim]   {marker}",
                    highlight=False,
                )

        if help:
            console.print(f"  [dim]{help}[/dim]", highlight=False)

        console.print()
        if exit:
            sys.exit(1)


class uError(uException):
    pass


class uSyntaxError(uException):
    pass


class uNameError(uException):
    pass


class uTypeError(uException):
    pass


class Dimension_Mismatch(uException):
    pass


class uCircularImport(uException):
    pass


class uImportError(uException):
    pass


class uModuleNotFound(uException):
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
            f"unexpected token '{tok.value}'",
            module=self.module,
            help=help,
            loc=tok.loc,
        )

    def unexpectedEOF(self, loc: Location | None = None):
        uSyntaxError(
            "unexpected end of file",
            module=self.module,
            loc=loc,
        )

    def binOpMismatch(self, node: BinOp, texts: list[str]):
        operation = {
            "add": "addition",
            "sub": "subtraction",
        }[node.op.name]

        Dimension_Mismatch(
            f"incompatible dimensions in {operation}: [{texts[0]}] vs [{texts[1]}]",
            module=self.module,
            loc=node.loc,
        )

    def binOpTypeMismatch(self, node: BinOp, left, right):
        operation = {
            "add": "+",
            "sub": "-",
            "mul": "*",
            "div": "/",
            "pow": "^",
            "mod": "%",
            "intdiv": "//",
        }[node.op.name]

        uTypeError(
            f"unsupported operand type(s) for '{operation}': '{left.typ}' and '{right.typ}'",
            module=self.module,
            loc=node.loc,
        )

    def nameError(self, name: Identifier):
        uNameError(
            f"name '{name.name}' is not defined",
            module=self.module,
            loc=name.loc,
        )

    def throw(
        self,
        exception: type[uException],
        message: str,
        help: str | None = None,
        loc: Location | None = None,
    ):
        exception(message=message, module=self.module, help=help, loc=loc)
