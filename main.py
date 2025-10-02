import json
import os
import pickle
import sys
from hashlib import sha512

from rich.console import Console

from module import Module

console = Console()

snapshots = {}

tests = sorted(os.listdir("tests"))
if len(sys.argv) > 1:
    tests = [test for test in tests if test.startswith(sys.argv[1])]

for test in tests:
    m = Module(path="tests/" + test)

    m.parse()
    m.dimcheck()

    snapshots[test] = sha512(pickle.dumps(m.ast)).hexdigest()

    print()
    console.print(test, "=" * 40, style="bold green")
    console.print(m.ast)


if os.path.isfile("snapshots.json"):
    with open("snapshots.json", "r") as saved:
        for name, snapshot in json.load(saved).items():
            if snapshots.get(name) != snapshot:
                console.print(f"Snapshot for {name} has changed", style="bold red")

with open("snapshots.json", "w") as saved:
    json.dump(snapshots, saved)
