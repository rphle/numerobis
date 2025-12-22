import subprocess
from pathlib import Path


def compile(code: str, output: str | Path = "output/output"):
    cflags = (
        subprocess.check_output(["pkg-config", "--cflags", "glib-2.0"], text=True)
        .strip()
        .split()
    )
    libs = (
        subprocess.check_output(["pkg-config", "--libs", "glib-2.0"], text=True)
        .strip()
        .split()
    )

    cmd = (
        ["gcc", "-x", "c", "-", "-Icompiler/runtime", "-o", str(output)]
        + cflags
        + libs
        + ["-lm"]
    )
    return subprocess.run(
        cmd,
        input=code,
        check=True,
        text=True,
        capture_output=True,
        encoding="utf-8",
    )


def run(path: str | Path = "output/output"):
    return subprocess.run(
        [str(path)],
        check=True,
        text=True,
        capture_output=True,
    )
