import argparse
import dataclasses
import itertools
import os
import re
import sys
import time
from collections import defaultdict
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Optional

import rich.markup
import rich.padding
from rich.console import Console
from tqdm import tqdm

from numerobis.module import Module
from runtime.build_lib import build_lib

console = Console()


@dataclass
class Test:
    file: str | Path
    line: int
    source: str
    throws: Optional[str] = None
    thrown: Optional[str] = None
    time: dict[str, float] = dataclasses.field(default_factory=dict)
    output: str = ""

    def module(self, builtins: bool = True):
        return Module(path=self.file, source=self.source, builtins=builtins)


def timeit(func):
    t0 = time.perf_counter()
    func()
    return time.perf_counter() - t0


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run Numerobis test suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "-v", "--verbose", action="store_true", help="Show output for failed tests only"
    )
    output_group.add_argument(
        "-f",
        "--full",
        action="store_true",
        help="Show output for all tests (passed and failed)",
    )

    code_group = parser.add_argument_group()
    code_group.add_argument(
        "-p",
        "--print",
        action="store_true",
        help="Print generated code (simple output)",
    )
    code_group.add_argument(
        "-F", "--format", action="store_true", help="Print formatted generated code"
    )

    parser.add_argument(
        "--cc",
        default="gcc",
        metavar="COMPILER",
        help="C compiler to use (default: gcc)",
    )

    # Test file selection
    parser.add_argument(
        "tests",
        nargs="*",
        metavar="TEST",
        help="Specific test files to run (without .nbis extension)",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    if not (args.verbose or args.full):
        args.verbose = True

    build_lib()

    tests_dir = Path("tests")
    files = sorted(os.listdir(tests_dir))

    # Filter test files
    if args.tests:
        files = [test for test in files if test.removesuffix(".nbis") in args.tests]

    # Print header
    console.print(
        "[bold]Running tests[/bold] "
        f"[dim]\\[mode={'full' if args.full else 'verbose' if args.verbose else 'quiet'}, "
        f"output={'simple' if args.print else 'formatted' if args.format else 'none'}, "
        f"compiler={args.cc}][/dim]",
        highlight=False,
    )

    if args.tests:
        console.print(
            f"[dim]Running {len(files)} selected test file(s)[/dim]",
            highlight=False,
        )

    # Parse test files
    tests: dict[str, tuple[Test, list[Test]]] = {}
    for file in files:
        path = tests_dir / file
        if path.is_dir():
            continue
        lines = open(path, "r", encoding="utf-8").readlines()
        chunks = [Test(path, 1, "")]
        for i, line in enumerate(lines):
            if match := re.match(r"# ((---+)|(E\d{3})|(///+))", line.strip()):
                throws = match.group(1) if not match.group(1).startswith("-") else None
                chunks.append(Test(path, i + 1, "", throws))
            else:
                chunks[-1].source += line
        tests[str(path)] = (chunks[0], chunks[1:])

    # Run tests
    with tqdm(
        total=sum(len(file[1]) for _, file in tests.items()), leave=False
    ) as pbar:
        errors = 0
        for file in tests:
            pbar.set_description(f"{Path(file).name}")
            pbar.refresh()
            header = tests[file][0].module()
            header.parse()
            header.typecheck()

            for i, test in enumerate(tests[file][1]):
                mod = test.module()
                mod.namespaces.update(header.namespaces)
                mod.namespaces.imports.update(header.namespaces.imports)

                output = StringIO()
                times = {}
                try:
                    with redirect_stdout(output), redirect_stderr(output):
                        print(mod.meta.source.strip())
                        print()
                        times["Parsing"] = timeit(mod.parse)
                        times["Typechecking"] = timeit(mod.typecheck)

                        mod.header = mod.header.merge(header.header)
                        mod.imports = header.imports[:-1] + mod.imports
                        times["Compilation"] = timeit(mod.compile)
                        times["Linking"] = timeit(
                            lambda: mod.link(
                                print_=args.print or args.format, format=args.format
                            )
                        )
                        times["GCC"] = timeit(lambda: mod.gcc(cache=True, cc=args.cc))
                        times["Execution"] = timeit(mod.run)

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

                tests[file][1][i].time = times

                error = re.search(r"\[(E\d{3})\]", output.getvalue())
                test.thrown = error.group(1) if error else None
                test.output = output.getvalue()

                if test.throws != test.thrown and test.throws != "///":
                    errors += 1

                pbar.update(1)
                pbar.set_postfix(errors=errors, line=test.line)

    # Print results
    cumulative = defaultdict(float)
    ratio = [0, 0]
    for test in itertools.chain.from_iterable(file[1] for _, file in tests.items()):
        if test.throws != test.thrown and test.throws != "///":
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
            if args.verbose or args.full:
                console.print(
                    rich.padding.Padding(
                        f"[dim]{rich.markup.escape(test.output)}[/dim]",
                        pad=(0, 0, 0, 2),
                    ),
                    highlight=False,
                    emoji=False,
                )
        else:
            if args.full:
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

        for key, value in test.time.items():
            cumulative[key] += value
        ratio[1] += 1

    # Print summary
    console.print("\n[bold][SUMMARY][/bold]")
    p, t = ratio
    ratio_pct = p / t if t > 0 else 0
    color = (
        "green"
        if ratio_pct == 1 or t == 0
        else "orange3"
        if ratio_pct >= 0.6
        else "red"
    )
    console.print(
        f"[bold {color}]{p}/{t}[/bold {color}] tests passed "
        f"[dim]([bold {color}]{ratio_pct:.2%}[/bold {color}])[/dim]"
    )

    total = sum(cumulative.values())
    console.print(
        f"[bold]Total time[/bold]: [bold cyan]{total:.3f}s[/bold cyan] "
        f"[dim]([bold cyan]{total / t if t > 0 else 0:.4f}s[/bold cyan] average)[/dim]"
    )
    for key, value in cumulative.items():
        console.print(
            f"  {key}: [bold cyan]{value:.3f}s[/bold cyan] "
            f"[dim]([bold cyan]{value / t if t > 0 else 0:.4f}s[/bold cyan] average)[/dim]"
        )

    sys.exit(0 if p == t else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("[bold red]Interrupted by user[/bold red]")
        sys.exit(1)
