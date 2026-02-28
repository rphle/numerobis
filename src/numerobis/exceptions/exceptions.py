"""Exception handling and formatted error reporting."""

import dataclasses
import sys
import textwrap
from importlib import resources
from typing import Any, Literal

import rich.console
import rich.markup

from ..classes import ModuleMeta
from ..nodes.ast import BinOp, BoolOp, Identifier
from ..nodes.core import Location, Token
from . import msgparser


@dataclasses.dataclass(frozen=True)
class Mismatch:
    kind: Literal["type", "dimension"]
    left: Any
    right: Any

    def __bool__(self) -> Literal[False]:
        return False


class uException:
    def __init__(
        self,
        message: msgparser.ErrorMessage,
        module: ModuleMeta,
        preview: bool = True,
        loc: Location | None = None,
        stack: list[Location] = [],
        exit: bool = True,
    ):
        console = rich.console.Console(force_terminal=True, stderr=True)

        for previous in stack:
            location = f"{module.path or '<unknown>'}" + (
                f":{previous.line}:{previous.col}" if previous else ""
            )
            console.print(
                f"[dim]at {location}[/dim]",
                highlight=False,
                emoji=False,
            )

        # Header
        location = f"{module.path or '<unknown>'}" + (
            f":{loc.line}:{loc.col}" if loc else ""
        )
        console.print(
            f"[bold red]{message.type}[/bold red] [dim]at {location}[/dim]",
            highlight=False,
            emoji=False,
        )
        console.print(
            f"  [dim][{message.code}][/dim] {message.message}", highlight=False
        )

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
                    f"[dim]{(min(5 - len(str(line.line)), 4) * ' ')}{line.line} │[/dim]   {prefix}{highlighted}{suffix}",
                    highlight=False,
                )

                underline = "─" * (line.end_col - line.col + 1)
                if i == 0:
                    underline = "╰" + underline[1:]
                if i == len(locs) - 1:
                    underline = underline[:-1] + "╯"
                marker = f"{' ' * len(f'{prefix}{src[start : line.col - 1]}')}[red bold]{underline}[/bold red]"

                console.print(
                    f"[dim]      |[/dim]   {marker}",
                    highlight=False,
                )

        if message.help:
            console.print(
                textwrap.indent(f"[dim]{rich.markup.escape(message.help)}[/dim]", "  "),
                highlight=False,
            )

        console.print()
        if exit:
            sys.exit(1)


class Exceptions:
    def __init__(self, module: ModuleMeta, stack: list[Location] = []):
        self.module = module
        self.stack = stack
        with resources.as_file(
            resources.files("numerobis.exceptions") / "messages.txt"
        ) as messages_path:
            self.codes = msgparser.parse(messages_path)

    def unexpectedToken(self, tok: Token, help: str | None = None):
        self.throw(1, token=tok.value, loc=tok.loc, help=help)

    def unexpectedEOF(self, loc: Location | None = None):
        self.throw(2, loc=loc)

    def binOpMismatch(self, node: BinOp | BoolOp, mismatch: Mismatch):
        left, right = mismatch.left, mismatch.right
        if mismatch.kind == "dimension":
            operation = {
                "add": "addition",
                "sub": "subtraction",
                "dadd": "addition",
                "dsub": "subtraction",
                "mod": "modulo operation",
            }[node.op.name]

            self.throw(
                703,
                operation=operation,
                left=left,
                right=right,
                loc=node.loc,
            )

        elif mismatch.kind == "type":
            operation = {
                "add": "+",
                "sub": "-",
                "dadd": "|+|",
                "dsub": "|-|",
                "mul": "*",
                "div": "/",
                "pow": "^",
                "mod": "%",
                "intdiv": "//",
            }.get(node.op.name, node.op.name)
            self.throw(502, operation=operation, left=left, right=right, loc=node.loc)

    def nameError(self, name: Identifier):
        self.throw(601, name=name.name, loc=name.loc)

    def invalidParameterNumber(self, node):
        self.throw(701, callee=node.callee.name, loc=node.loc)

    def throw(
        self, code: int, loc: Location | None = None, help: str | None = None, **kwargs
    ):
        try:
            message = dataclasses.replace(self.codes[f"E{code:03d}"])  # copy
        except KeyError:
            raise ValueError(f"Unknown error code: {code}")

        message.message = message.message.format(**kwargs)
        if help:
            message.help = help

        uException(message=message, module=self.module, loc=loc)
