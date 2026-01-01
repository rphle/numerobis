import subprocess
from pathlib import Path

try:
    from gcc import _pkg
except ImportError:
    from .gcc import _pkg


def build_lib():
    glib_cflags, _ = _pkg("glib-2.0")
    gc_cflags, _ = _pkg("bdw-gc")

    runtime_root = Path("compiler/runtime")
    sources = list(runtime_root.rglob("*.c"))
    object_files = []

    for src in sources:
        obj = src.with_suffix(".o")
        subprocess.run(
            [
                "gcc",
                "-c",
                str(src),
                "-o",
                str(obj),
                "-Icompiler/runtime",
                *glib_cflags,
                *gc_cflags,
                "-fPIC",
            ],
            check=True,
        )
        object_files.append(str(obj))

    subprocess.run(
        ["ar", "rcs", "compiler/runtime/libruntime.a"] + object_files, check=True
    )

    print("Static library created at compiler/runtime/libruntime.a")


if __name__ == "__main__":
    build_lib()
