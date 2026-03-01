"""Build system for compiling runtime C library and generating message headers.

Compiles C sources into object files, creates static library, and generates
C headers from message definitions.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

from numerobis.compiler.gcc import _pkg
from numerobis.compiler.utils import repr_double
from numerobis.exceptions import msgparser


def build_lib():
    generate_messages()

    glib_cflags, _ = _pkg("glib-2.0")
    gc_cflags, _ = _pkg("bdw-gc")

    script_dir = Path(__file__).parent.resolve()
    runtime_root = script_dir
    dest_runtime = script_dir.parent / "src" / "numerobis" / "runtime"

    if dest_runtime.exists():
        shutil.rmtree(dest_runtime)
    os.makedirs(dest_runtime, exist_ok=True)

    sources = [f for f in runtime_root.rglob("*.c") if f.name != "source.c"]
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
                "-Iruntime",
                *glib_cflags,
                *gc_cflags,
                "-fPIC",
            ],
            check=True,
        )
        object_files.append(str(obj))

    subprocess.run(
        ["ar", "rcs", str(dest_runtime / "libruntime.a")] + object_files, check=True
    )

    # Mirror the .h files
    for h_file in runtime_root.rglob("*.h"):
        target_path = dest_runtime / h_file.relative_to(runtime_root)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(h_file, target_path)

    print(f"Static library and headers created at {dest_runtime}")


def generate_messages(
    categories: tuple = (3, 9), target="runtime/numerobis/exceptions/messages.h"
):
    categories = tuple(str(c) for c in categories)
    messages = {
        code: msg
        for code, msg in msgparser.parse(
            "src/numerobis/exceptions/messages.txt"
        ).items()
        if code[1] in categories
    }

    struct = []
    for msg in messages.values():
        fields = [msg.code[1:]] + [
            repr_double(v) if v is not None else "NULL"
            for v in (msg.type, msg.message, msg.help)
        ]
        struct.append(f"{{ {', '.join(fields)} }}")

    struct = ", ".join(struct)

    content = open(target, "r", encoding="utf-8").read()
    content = re.sub(
        r"<CONTENT>.*</CONTENT>",
        f"<CONTENT> */\n{struct}\n/* </CONTENT>",
        content,
        flags=re.MULTILINE | re.DOTALL,
    )
    content = subprocess.run(
        ["clang-format"], input=content, text=True, capture_output=True
    ).stdout
    open(target, "w", encoding="utf-8").write(content)

    print(f"Messages file created at {target}")


if __name__ == "__main__":
    build_lib()
