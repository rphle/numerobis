"""Test runner.

Parses .nbis test files with inline test annotations and executes them,
reporting pass/fail status and performance metrics.
"""

import argparse
import os
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Optional

import rich.markup
import rich.padding
from rich.console import Console
from tqdm import tqdm

from numerobis.module import Module
from runtime.build_lib import build_lib

os.makedirs("output", exist_ok=True)
console = Console()


@dataclass
class TestResult:
    file_name: str
    file_path: str
    line: int
    throws: Optional[str]
    thrown: Optional[str] = None
    output: str = ""
    times: dict[str, float] = field(default_factory=dict)
    success: bool = False


def timeit(func):
    t0 = time.perf_counter()
    func()
    return time.perf_counter() - t0


def run_single_test(
    file_path,
    header_source,
    test_source,
    line,
    throws,
    cc,
    linker,
    print_code,
    format_code,
    use_cmake,
    use_ccache,
    run_exec=True,
):
    output = StringIO()
    times = {}
    thrown_error = None
    output_bin = f"output/bin_{abs(hash((str(file_path), line)))}"

    try:
        with redirect_stdout(output), redirect_stderr(output):
            header_mod = Module(path=file_path, source=header_source)
            header_mod.parse()
            header_mod.typecheck()

            mod = Module(path=file_path, source=test_source)
            mod.namespaces.update(header_mod.namespaces)
            mod.namespaces.imports.update(header_mod.namespaces.imports)

            print(mod.meta.source.strip())
            print()

            times["Parsing"] = timeit(mod.parse)
            times["Typechecking"] = timeit(mod.typecheck)

            mod.header = mod.header.merge(header_mod.header)
            mod.imports = header_mod.imports[:-1] + mod.imports

            times["Compilation"] = timeit(mod.compile)
            times["Linking"] = timeit(
                lambda: mod.link(print_=print_code or format_code, format=format_code)
            )

            times["C Compiler"] = timeit(
                lambda: mod.cmake(
                    output_path=output_bin,
                    cc=cc,
                    linker=linker,
                    use_cmake=use_cmake,
                    use_ccache=use_ccache,
                )
            )

            if run_exec:

                def run():
                    code = 0
                    try:
                        code = mod.run(path=output_bin)
                    except SystemExit as e:
                        code = e.code
                    if code != 0:
                        print(f"[E303]: {code}")

                times["Execution"] = timeit(run)

    except SystemExit:
        pass

    out_str = output.getvalue()
    error_match = re.search(r"\[(E\d{3})\]", out_str)
    thrown_error = error_match.group(1) if error_match else None

    success = (throws == thrown_error) or (throws == "///")

    return TestResult(
        file_name=Path(file_path).name,
        file_path=str(file_path),
        line=line,
        throws=throws,
        thrown=thrown_error,
        output=out_str,
        times=times,
        success=success,
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Run Numerobis test suite")
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "-v", "--verbose", action="store_true", help="Show failed tests"
    )
    output_group.add_argument(
        "-f", "--full", action="store_true", help="Show all tests"
    )
    parser.add_argument(
        "-p", "--print", action="store_true", help="Print generated code"
    )
    parser.add_argument(
        "-F", "--format", action="store_true", help="Print formatted code"
    )
    parser.add_argument("--cc", default="gcc", help="C compiler")
    parser.add_argument("--linker", default=None, help="C linker")
    parser.add_argument(
        "-j", "--jobs", type=int, default=os.cpu_count() or 4, help="Parallel jobs"
    )
    parser.add_argument(
        "--no-cmake",
        dest="use_cmake",
        action="store_false",
        default=True,
        help="Skip CMake and use direct GCC bindings (potentially unstable)",
    )
    parser.add_argument(
        "--no-lib",
        action="store_true",
        help="Skip re-building the static runtime libraries",
    )
    parser.add_argument(
        "--ccache",
        dest="use_ccache",
        action="store_true",
        help="Use ccache to speed up recompilation.",
    )

    parser.add_argument("tests", nargs="*", help="Specific tests to run")
    return parser.parse_args()


def main():
    args = parse_args()
    if not (args.verbose or args.full):
        args.verbose = True

    if not args.no_lib:
        build_lib()
        print()

    tests_dir = Path("tests")
    examples_dir = Path("examples")

    files = sorted([f for f in os.listdir(tests_dir) if f.endswith(".nbis")])
    example_files = sorted([f for f in os.listdir(examples_dir) if f.endswith(".nbis")])

    if args.tests:
        files = [f for f in files if f.removesuffix(".nbis") in args.tests]
        example_files = example_files if "examples" in args.tests else []

    console.print(
        "[bold]Running tests[/bold] "
        f"[dim]\\[mode={'full' if args.full else 'verbose' if args.verbose else 'quiet'}, "
        f"output={'simple' if args.print else 'formatted' if args.format else 'none'}, "
        f"compiler={args.cc}, "
        f"linker={args.linker if args.linker else 'default'}, "
        f"cmake={str(args.use_cmake).lower()}, "
        f"ccache={str(args.use_ccache).lower()}][/dim]",
        highlight=False,
    )
    if args.tests:
        console.print(
            f"[dim]Running {len(files)} selected test file(s)[/dim]", highlight=False
        )

    actual_time = time.time()

    test_queue = []
    # standard tests
    for file in files:
        path = tests_dir / file
        lines = open(path, "r", encoding="utf-8").readlines()
        header_src, chunk_src, curr_line, curr_throws, first = "", "", 1, None, True

        for i, line in enumerate(lines):
            if match := re.match(r"# ((---+)|(E\d{3})|(///+))", line.strip()):
                if first:
                    header_src, first = chunk_src, False
                else:
                    test_queue.append(
                        (path, header_src, chunk_src, curr_line, curr_throws, True)
                    )
                curr_throws = (
                    match.group(1) if not match.group(1).startswith("-") else None
                )
                chunk_src, curr_line = "", i + 2
            else:
                chunk_src += line
        test_queue.append((path, header_src, chunk_src, curr_line, curr_throws, True))

    # example files
    for file in example_files:
        path = examples_dir / file
        with open(path, "r", encoding="utf-8") as f:
            test_queue.append((path, "", f.read(), 1, None, False))

    results: list[TestResult] = []
    fail_count = 0
    with ProcessPoolExecutor(max_workers=args.jobs) as executor:
        futures = [
            executor.submit(
                run_single_test,
                p,
                h,
                c,
                ll,
                t,
                args.cc,
                args.linker,
                args.print,
                args.format,
                args.use_cmake,
                args.use_ccache,
                run_exec,
            )
            for p, h, c, ll, t, run_exec in test_queue
        ]

        with tqdm(total=len(futures), leave=False) as pbar:
            for future in as_completed(futures):
                res = future.result()
                results.append(res)
                if not res.success:
                    fail_count += 1

                pbar.set_description(f"{res.file_name}")
                pbar.set_postfix(errors=fail_count, line=res.line)
                pbar.update(1)

    results.sort(key=lambda x: (x.file_path, x.line))
    cumulative = defaultdict(float)
    passed = 0

    for res in results:
        if not res.success:
            text = (
                (f"expected [bold]{res.throws}[/bold]" if res.throws else "")
                + (", " if res.throws and res.thrown else "")
                + (f"raised [bold]{res.thrown}[/bold]" if res.thrown else "")
            )
            console.print(
                f"[bold red][FAIL][/bold red] [red]{res.file_path}:{res.line}[/red]: {text}",
                highlight=False,
            )
            if args.verbose or args.full:
                console.print(
                    rich.padding.Padding(
                        f"[dim]{rich.markup.escape(res.output)}[/dim]", (0, 0, 0, 2)
                    ),
                    highlight=False,
                )
        else:
            passed += 1
            if args.full:
                console.print(
                    f"[bold green][PASS][/bold green] [green]{res.file_path}:{res.line}[/green]",
                    highlight=False,
                )
                console.print(
                    rich.padding.Padding(
                        f"[dim]{rich.markup.escape(res.output)}[/dim]", (0, 0, 0, 2)
                    ),
                    highlight=False,
                )

        for k, v in res.times.items():
            cumulative[k] += v

    console.print("\n[bold][SUMMARY][/bold]")
    t = len(results)
    ratio_pct = passed / t if t > 0 else 0
    color = (
        "green"
        if ratio_pct == 1 or t == 0
        else "orange3"
        if ratio_pct >= 0.6
        else "red"
    )

    console.print(
        f"[bold {color}]{passed}/{t}[/bold {color}] tests passed "
        f"[dim]([bold {color}]{ratio_pct:.2%}[/bold {color}])[/dim]",
        highlight=False,
    )

    total_time = sum(cumulative.values())
    console.print(
        f"[bold]Total time[/bold]: [bold cyan]{total_time:.3f}s[/bold cyan] "
        f"[dim]([bold cyan]{total_time / t if t > 0 else 0:.4f}s[/bold cyan] average, "
        f"[bold cyan]{time.time() - actual_time:.4f}s[/bold cyan] real)[/dim]",
        highlight=False,
    )

    for key, value in cumulative.items():
        console.print(
            f"  {key}: [bold cyan]{value:.3f}s[/bold cyan] "
            f"[dim]([bold cyan]{value / t if t > 0 else 0:.4f}s[/bold cyan] average)[/dim]",
            highlight=False,
        )

    sys.exit(0 if passed == t else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("[bold red]Interrupted by user[/bold red]")
        sys.exit(1)
