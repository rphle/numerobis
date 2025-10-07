import json
import os
import pickle
import sys
from hashlib import sha512
from pathlib import Path

from rich.console import Console

from module_system import ModuleSystem

console = Console()

snapshots = {}
tests_dir = Path("tests")
tests = sorted(os.listdir(tests_dir))


if len(sys.argv) > 1:
    tests = [test for test in tests if test.startswith(sys.argv[1])]

module_system = ModuleSystem()
for test in tests:
    print()
    console.print(f"{test} {'=' * 40}", style="bold green")

    module_info = module_system.load(str(tests_dir / test))
    snapshots[test] = sha512(pickle.dumps(module_info.module.ast)).hexdigest()

    console.print(module_info.module.ast)

if os.path.isfile("snapshots.json"):
    with open("snapshots.json", "r") as saved:
        for name, snapshot in json.load(saved).items():
            if snapshots.get(name) != snapshot:
                console.print(f"Snapshot for {name} has changed", style="bold red")

with open("snapshots.json", "w") as saved:
    json.dump(snapshots, saved)
