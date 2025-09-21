import json
import os
import pickle
import sys
from hashlib import sha512
from parser import Parser

from rich.console import Console

from lexer import lex

console = Console()

snapshots = {}

tests = sorted(os.listdir("tests"))
if len(sys.argv) > 1:
    tests = [test for test in tests if test.startswith(sys.argv[1])]

for test in tests:
    source = open(f"tests/{test}", "r").read()

    lexed = lex(source, debug=False)
    parser = Parser(lexed, path=test)
    try:
        parsed = parser.start()
    except Exception as e:
        console.print(f"Error parsing {test}:", style="bold red")
        raise e

    snapshots[test] = sha512(pickle.dumps(parsed)).hexdigest()

    print()
    console.print(test, "=" * 40, style="bold green")
    console.print(parsed)


if os.path.isfile("snapshots.json"):
    with open("snapshots.json", "r") as saved:
        for name, snapshot in json.load(saved).items():
            if snapshots.get(name) != snapshot:
                console.print(f"Snapshot for {name} has changed", style="bold red")

with open("snapshots.json", "w") as saved:
    json.dump(snapshots, saved)
