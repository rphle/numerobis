import platform
import time
from pathlib import Path

import click
import rich
import rich.syntax
from rich.console import Console

from .. import __version__
from ..compiler import gcc as gnucc
from ..module import Module

console = Console()


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(
    version=__version__,
    prog_name="Numerobis",
    message=f"%(prog)s, version %(version)s (Python {platform.python_version()})",
)
def cli() -> None:
    pass


@cli.command("build")
@click.argument("source", type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.option(
    "-o",
    "--output",
    default="",
    show_default=False,
    help="Output binary path",
)
@click.option(
    "--run/--no-run",
    "should_run",
    default=False,
    help="Execute the produced binary after building",
)
@click.option(
    "--quiet",
    is_flag=True,
    help="Suppress non-essential compiler output.",
)
@click.option(
    "--debug/--no-debug",
    default=True,
    help="Emit debug information (-g).",
)
@click.option(
    "-O",
    "opt_level",
    type=click.Choice(["0", "1", "2", "3", "s"]),
    default="0",
    help="Set optimization level (passed to the C compiler).",
)
@click.option(
    "--cc",
    "cc",
    type=click.STRING,
    default="gcc",
    help="Set C compiler to use.",
)
def build(
    source: str,
    output: str,
    should_run: bool,
    quiet: bool,
    debug: bool,
    opt_level: str,
    cc: str,
) -> None:
    """
    Compile SOURCE (.nbis) into a native executable.
    """

    t0 = time.time()

    if not output:
        stem = Path(Path(source).stem).resolve()
        if stem.is_dir():
            console.print("[red]Output path is a directory[/red]")
            raise SystemExit(1)
        output = str(stem)
    else:
        output = str(Path(output).resolve())

    flags = set()
    if debug:
        flags.add("-g")
    flags.add(f"-O{opt_level}")

    try:
        mod = Module(source)
        mod.load()
        mod.link(format=False)
        mod.gcc(output, flags=flags, cc=cc)
    except KeyboardInterrupt:
        console.print("[red]Build interrupted by user[/red]")
        raise SystemExit(130)

    if not quiet:
        console.print(
            f"[green]Built {output} ({time.time() - t0:.2f}s)[/green]",
            highlight=False,
        )

    if should_run:
        gnucc.run(path=output, capture_output=False)


@cli.command("view")
@click.argument(
    "source",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
)
@click.option(
    "-o",
    "--output",
    default="",
    show_default=False,
    help="Write the generated C code to a file instead of printing it.",
)
@click.option(
    "--theme",
    default="monokai",
    show_default=True,
    help="Rich syntax highlighting theme to use when printing code.",
)
@click.option(
    "--line-numbers/--no-line-numbers",
    default=True,
    help="Show line numbers when printing code.",
)
def view(
    source: str,
    output: str,
    theme: str,
    line_numbers: bool,
) -> None:
    try:
        mod = Module(source)
        mod.load()
        mod.link(format=True)
    except KeyboardInterrupt:
        console.print("[red]Operation interrupted by user[/red]")
        raise SystemExit(130)

    assert mod.linker
    code = mod.linker.linked

    if output:
        try:
            out_path = Path(output).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(code)
            console.print(f"[green]Generated C code written to {out_path}[/green]")
        except Exception as e:
            console.print(f"[red]Failed to write to {output}: {e}[/red]")
            raise SystemExit(1)
    else:
        console.print(
            rich.syntax.Syntax(
                code,
                "c",
                theme=theme,
                line_numbers=line_numbers,
                background_color="default",
            )
        )
