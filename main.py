import json
import os
import pickle
import sys
from hashlib import sha512
from pathlib import Path

from rich.console import Console

from module import Module

console = Console()

snapshots = {}
tests_dir = Path("tests")
tests = sorted(os.listdir(tests_dir))


if len(sys.argv) > 1:
    tests = [test for test in tests if test.startswith(sys.argv[1])]

for test in tests:
    print()
    console.print(f"{test} {'=' * 40}", style="bold green")

    mod = Module(path=tests_dir / test)
    mod.process()

    snapshots[test] = sha512(pickle.dumps(mod.ast)).hexdigest()

    console.print(mod.ast)

if os.path.isfile("snapshots.json"):
    with open("snapshots.json", "r") as saved:
        for name, snapshot in json.load(saved).items():
            if snapshots.get(name) != snapshot:
                console.print(f"Snapshot for {name} has changed", style="bold red")

with open("snapshots.json", "w") as saved:
    json.dump(snapshots, saved)
