import os
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from classes import ModuleMeta
from compiler.utils import repr_double


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


def compile(code: str, module: ModuleMeta, output: str | Path = "output/output"):
    glib_cflags, glib_libs = _pkg("glib-2.0")
    gc_cflags, gc_libs = _pkg("bdw-gc")

    struct = """
    typedef struct {
        const char *filename;
        int count;
        const char *lines[];
    } UnidadProgram;
    """

    source = f"const UnidadProgram UNIDAD_PROGRAM = {{ {repr_double(str(module.path))}, {len(module.source.split('\n'))}, {repr_double(module.source).replace('\\n', '", "')} }};"

    tmp_source = tempfile.NamedTemporaryFile(delete=False, suffix=".c")
    tmp_source.write((struct + source).encode("utf-8"))
    tmp_source.close()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".c")
    tmp.write(code.encode("utf-8"))
    tmp.close()

    cmd = (
        ["gcc"]
        + ["-pipe"]
        + [tmp.name, tmp_source.name]
        + ["-o", str(output)]
        + ["-Icompiler/runtime"]
        + glib_cflags
        + gc_cflags
        + ["compiler/runtime/libruntime.a"]
        + glib_libs
        + gc_libs
        + ["-lm"]
        + ["-O0", "-g"]
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
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(
                proc.returncode, cmd, output=proc.stdout, stderr=proc.stderr
            )
        return proc
    finally:
        os.unlink(tmp.name)
        os.unlink(tmp_source.name)


def run(path: str | Path = "output/output"):
    return subprocess.run(
        [str(path)],
        check=False,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
