"""Command-line interface for Numerobis compiler."""

import platform
import time
from pathlib import Path
from typing import Optional

import click
import rich
import rich.syntax
from rich.console import Console

from numerobis.utils import is_unix

from .. import __version__
from ..compiler import gcc as gnucc
from ..module import Module

console = Console()


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(
    version=__version__,
    prog_name="Numerobis",
    message=f"%(prog)s, version %(version)s (Python {platform.python_version()} on {'UNIX' if is_unix else 'Windows'})",
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
@click.option(
    "--linker",
    "linker",
    type=click.STRING,
    default=None,
    help="Set C linker to use.",
)
@click.option(
    "--cmake/--no-cmake",
    "use_cmake",
    default=True,
    help="Use CMake for build configuration.",
)
@click.option(
    "--ccache/--no-ccache",
    "use_ccache",
    default=False,
    help="Use ccache to speed up recompilation.",
)
def build(
    source: str,
    output: str,
    should_run: bool,
    quiet: bool,
    debug: bool,
    opt_level: str,
    cc: str,
    linker: Optional[str],
    use_cmake: bool,
    use_ccache: bool,
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
        if not is_unix:
            output += ".exe"
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
        t1 = time.time()
        mod.cmake(
            output,
            flags=flags,
            cc=cc,
            linker=linker if linker else None,
            use_cmake=use_cmake,
            use_ccache=use_ccache,
        )
    except KeyboardInterrupt:
        console.print("[red]Build interrupted by user[/red]")
        raise SystemExit(130)

    if not quiet:
        graphics_suffix = (
            " [blue dim](+gfx)[/blue dim]"
            if mod.linker and mod.linker._uses_graphics()
            else ""
        )

        console.print(
            f"[green]Built {output}[/green]{graphics_suffix} [green]({t1 - t0:.2f}s / {time.time() - t0:.2f}s)[/green]",
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
