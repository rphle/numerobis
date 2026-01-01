import re
import subprocess
from pathlib import Path

from exceptions import msgparser

try:
    from gcc import _pkg

    from utils import repr_double  # type: ignore
except ImportError:
    from .gcc import _pkg
    from .utils import repr_double


def build_lib():
    generate_messages()

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


def generate_messages(
    categories: tuple = (9,), target="compiler/runtime/unidad/exceptions/messages.h"
):
    categories = tuple(str(c) for c in categories)
    messages = {
        code: msg
        for code, msg in msgparser.parse("exceptions/messages.txt").items()
        if code[1] in categories
    }

    struct = []
    for msg in messages.values():
        fields = [
            repr_double(v) if v is not None else "NULL"
            for v in (msg.code, msg.type, msg.message, msg.help)
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
