import itertools
import os
import re
import sys
import time
from contextlib import redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Optional

import rich.markup
import rich.padding
from rich.console import Console
from tqdm import tqdm

from module import Module

console = Console()


@dataclass
class Test:
    file: str | Path
    line: int
    source: str
    throws: Optional[str] = None
    thrown: Optional[str] = None
    time: float = -1
    output: str = ""

    def module(self):
        return Module(path=self.file, source=self.source)


times_per_test = {}
tests_dir = Path("tests")
files = sorted(os.listdir(tests_dir))
verbose = "--verbose" in sys.argv
full = "--full" in sys.argv


if len(sys.argv) - verbose > 1:
    files = [test for test in files if test.removesuffix(".und") in sys.argv[1:]]

tests: dict[str, tuple[Test, list[Test]]] = {}
for file in files:
    path = tests_dir / file
    lines = open(path, "r", encoding="utf-8").readlines()
    chunks = [Test(path, 1, "")]
    for i, line in enumerate(lines):
        if match := re.match(r"# ((---+)|(E\d{3})|(///+))", line.strip()):
            throws = match.group(1) if not match.group(1).startswith("-") else None
            chunks.append(Test(path, i + 1, "", throws))
        else:
            chunks[-1].source += line + "\n"
    tests[str(path)] = (chunks[0], chunks[1:])

with tqdm(total=sum(len(file[1]) for _, file in tests.items()), leave=False) as pbar:
    for file in tests:
        pbar.desc = file
        pbar.refresh()
        header = tests[file][0].module()
        header.process()

        for i, test in enumerate(tests[file][1]):
            mod = test.module()
            mod.namespaces.update(header.namespaces)

            output = StringIO()
            t0 = time.perf_counter()
            try:
                with redirect_stdout(output):
                    mod.process()
            except SystemExit:
                pass
            except Exception as e:
                if not test.throws == "///":
                    print(output.getvalue())
                    console.print(
                        f"[bold red][FAIL] [/bold red][red]{test.file}:{test.line}[/red]",
                        highlight=False,
                        emoji=False,
                    )
                    raise e
            tests[file][1][i].time = time.perf_counter() - t0

            error = re.search(r"\[(E\d{3})\]", output.getvalue())

            test.thrown = error.group(1) if error else None
            test.output = output.getvalue()
            pbar.update(1)


cumulative = 0
ratio = [0, 0]
for test in itertools.chain.from_iterable(file[1] for _, file in tests.items()):
    if test.throws != test.thrown:
        text = (
            (f"expected [bold]{test.throws}[/bold]" if test.throws else "")
            + (", " if test.throws and test.thrown else "")
            + (f"raised [bold]{test.thrown}[/bold]" if test.thrown else "")
        )
        console.print(
            f"[bold red][FAIL] [/bold red][red]{test.file}:{test.line}[/red]: {text}",
            highlight=False,
            emoji=False,
        )
        if verbose or full:
            console.print(
                rich.padding.Padding(
                    f"[dim]{rich.markup.escape(test.output)}[/dim]",
                    pad=(0, 0, 0, 2),
                ),
                highlight=False,
                emoji=False,
            )
    else:
        if full:
            console.print(
                f"[bold green][PASS] [/bold green][green]{test.file}:{test.line}[/green]",
                highlight=False,
                emoji=False,
            )
            console.print(
                rich.padding.Padding(
                    f"[dim]{rich.markup.escape(test.output)}[/dim]",
                    pad=(0, 0, 0, 2),
                ),
                highlight=False,
                emoji=False,
            )
        ratio[0] += 1

    cumulative += test.time
    ratio[1] += 1

console.print("[bold][SUMMARY][/bold]")
p, t = ratio
ratio = p / t if t > 0 else 0
color = "green" if ratio == 1 or t == 0 else "orange3" if ratio >= 0.6 else "red"
console.print(
    f"[bold {color}]{p}/{t}[reset] tests passed "
    f"[dim]([bold {color}]{ratio:.2%}[/bold {color}])[/dim]"
)
console.print(
    f"Total time: [bold cyan]{cumulative:.3f}s[/bold cyan] "
    f"[dim]([bold cyan]{cumulative / t if t > 0 else 0:.3f}s[/bold cyan] average)[/dim]"
)
