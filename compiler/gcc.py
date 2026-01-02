import os
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=None)
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


def compile(code: str, output: str | Path = "output/output"):
    glib_cflags, glib_libs = _pkg("glib-2.0")
    gc_cflags, gc_libs = _pkg("bdw-gc")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".c")

    tmp.write(code.encode("utf-8"))
    tmp.flush()
    tmp.close()

    cmd = (
        ["gcc", str(tmp.name), "-o", str(output)]
        + ["-Icompiler/runtime"]
        + glib_cflags
        + gc_cflags
        + [
            "compiler/runtime/libruntime.a",
            "compiler/runtime/unidad/exceptions/source.c",
        ]
        + glib_libs
        + gc_libs
        + ["-lm"]
    )

    try:
        proc = subprocess.run(
            cmd,
            check=False,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode == 0:
            return proc

        raise subprocess.CalledProcessError(
            proc.returncode, cmd, output=proc.stdout, stderr=proc.stderr
        )
    finally:
        os.unlink(tmp.name)


def run(path: str | Path = "output/output"):
    return subprocess.run(
        [str(path)],
        check=False,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
