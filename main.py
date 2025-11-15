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

update, args = (
    next((True for a in sys.argv[1:] if a == "--update"), False),
    [a for a in sys.argv[1:] if a != "--update"],
)
if args:
    tests = [test for test in tests if test.removesuffix(".und") in args]

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
                console.print(f"{name} has changed", style="bold red")

if update:
    with open("snapshots.json", "w") as saved:
        json.dump(snapshots, saved)
