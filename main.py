import json
import os
import pickle
import sys
import time
from hashlib import sha512
from pathlib import Path

from rich.console import Console
from rich.table import Table
from tqdm import tqdm

from module import Module

console = Console()

snapshots = {}
times_per_test = {}
tests_dir = Path("tests")
tests = sorted(os.listdir(tests_dir))

update, args = (
    next((True for a in sys.argv[1:] if a == "--update"), False),
    [a for a in sys.argv[1:] if a != "--update"],
)
if args:
    tests = [test for test in tests if test.removesuffix(".und") in args]

with tqdm(total=len(tests), leave=False) as pbar:
    for test in tests:
        pbar.desc = test

        start = time.perf_counter()
        mod = Module(path=tests_dir / test)
        mod.process()
        dur = time.perf_counter() - start

        times_per_test[test] = dur
        snapshots[test] = sha512(pickle.dumps(mod.ast)).hexdigest()

        pbar.update(1)


sorted_tests = sorted(times_per_test.items(), key=lambda x: x[1])

total_time = sum(t for _, t in sorted_tests)
cumulative = 0.0

table = Table(title="Performance")
table.add_column("Test", style="bold")
table.add_column("Time (s)", justify="right")
table.add_column("Cumulative (s)", justify="right")
table.add_column("% of total", justify="right")

for name, t in sorted_tests:
    cumulative += t
    table.add_row(
        name,
        f"{t:.3f}",
        f"{cumulative:.3f}",
        f"{(t / total_time) * 100:5.1f}%",
    )

table.add_row("", "", "", "")
table.add_row(
    "[bold]TOTAL[/bold]",
    f"[bold]{total_time:.3f}[/bold]",
    "",
    "100%",
)

console.print()
console.print(table)


if os.path.isfile("snapshots.json"):
    with open("snapshots.json", "r") as saved:
        for name, snapshot in json.load(saved).items():
            if snapshots.get(name) != snapshot:
                console.print(f"{name} has changed", style="bold red")

if update:
    with open("snapshots.json", "w") as saved:
        json.dump(snapshots, saved)
