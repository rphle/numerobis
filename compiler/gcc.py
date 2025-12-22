import subprocess
from pathlib import Path


def _pkg(name: str):
    cflags = (
        subprocess.check_output(["pkg-config", "--cflags", name], text=True)
        .strip()
        .split()
    )
    libs = (
        subprocess.check_output(["pkg-config", "--libs", name], text=True)
        .strip()
        .split()
    )
    return cflags, libs


def compile(
    code: str, output: str | Path = "output/output", include: list[str | Path] = []
):
    glib_cflags, glib_libs = _pkg("glib-2.0")
    gc_cflags, gc_libs = _pkg("bdw-gc")

    include = [f"compiler/runtime/{f}.c" for f in include]

    cmd = (
        ["gcc", "-x", "c", "-", "-o", str(output)]
        + [f for f in include if Path(f).is_file()]
        + ["-Icompiler/runtime"]
        + glib_cflags
        + gc_cflags
        + glib_libs
        + gc_libs
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
