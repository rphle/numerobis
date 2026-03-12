import os
import subprocess
from collections import defaultdict
from pathlib import Path

from tqdm import tqdm

path = Path(__file__).parent.resolve()
out = path / "out"

os.makedirs(out, exist_ok=True)


actions = {
    "py": {"compile": "cp {src} {bin}", "run": "python3 {bin}"},
    "c": {"compile": "gcc {src} -o {bin}", "run": "{bin}"},
    "nbis": {"compile": "nbis build {src} -o {bin}", "run": "{bin}"},
}


files = os.listdir(path / "src")
tests = defaultdict(dict)
for file in files:
    filepath = path / "src" / file
    name = filepath.stem
    ending = filepath.suffix[1:]
    if ending not in actions:
        continue
    tests[name][ending] = {"src": filepath, "bin": out / (filepath.name + ".bin")}

print(f"Collected {len(tests)} tests")

with tqdm(total=len(tests) * len(actions), desc="Compiling tests") as pbar:
    for name, test in tests.items():
        for ending, filepath in test.items():
            src = filepath["src"]
            bin = filepath["bin"]

            cmd = actions[ending]["compile"].format(bin=bin, src=src)
            subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL)
            pbar.update()


print("\n" + "=" * 80)
print("Starting Benchmarks")
print("=" * 80 + "\n")

for name, test in tests.items():
    print("\n" + "#" * 80)
    print(f"# Benchmark: {name}")
    print("#" * 80 + "\n")

    for ending, filepath in test.items():
        bin_path = filepath["bin"]

        if not bin_path.exists():
            continue

        run_cmd = actions[ending]["run"].format(bin=bin_path)

        print("-" * 60)
        print(f"Language: {ending}")
        print(f"Command : {run_cmd}")
        print("-" * 60)

        benchmark_cmd = f"hyperfine -N --warmup 10 --runs 50 --style basic '{run_cmd}'"

        subprocess.run(benchmark_cmd, shell=True)
        print()
