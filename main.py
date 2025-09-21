import json
import os
import pickle
from hashlib import sha512
from parser import Parser

from rich.console import Console

from lexer import lex

console = Console()

snapshots = {}

tests = os.listdir("tests")

for test in tests:
    source = open(f"tests/{test}", "r").read()

    lexed = lex(source, debug=False)
    parser = Parser(lexed)
    parsed = parser.start()

    snapshots[test] = sha512(pickle.dumps(parsed)).hexdigest()

    print()
    console.print(test, "=" * 40, style="bold green")
    console.print(parsed)


if os.path.isfile("snapshots.json"):
    with open("snapshots.json", "r") as saved:
        for name, snapshot in json.load(saved).items():
            if snapshots[name] != snapshot:
                console.print(f"Snapshot for {name} has changed", style="bold red")

with open("snapshots.json", "w") as saved:
    json.dump(snapshots, saved)
