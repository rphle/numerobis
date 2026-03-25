"""Build system for compiling runtime C library and generating message headers.

Compiles C sources into a static library via CMake, and generates
C headers from message definitions.
"""

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from numerobis.compiler.cmake import _run_subprocess
from numerobis.compiler.utils import repr_double
from numerobis.exceptions import msgparser


def build_lib():
    generate_messages()

    script_dir = Path(__file__).parent.resolve()
    runtime_root = script_dir
    dest_runtime = script_dir.parent / "src" / "numerobis" / "runtime"

    if dest_runtime.exists():
        shutil.rmtree(dest_runtime)
    os.makedirs(dest_runtime, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Collect all .c sources (excluding generated source.c)
        sources = [f for f in runtime_root.rglob("*.c") if f.name != "source.c"]
        source_list = "\n    ".join(str(s.as_posix()) for s in sources)

        cmakelists = f"""\
cmake_minimum_required(VERSION 3.10)
project(NumerobisRuntime C)

find_package(PkgConfig REQUIRED)
pkg_check_modules(GLIB REQUIRED glib-2.0)
pkg_check_modules(GC REQUIRED bdw-gc)

set(RUNTIME_SOURCES
    {source_list}
)

add_library(runtime STATIC ${{RUNTIME_SOURCES}})

target_include_directories(runtime PRIVATE
    "{runtime_root.as_posix()}"
    ${{GLIB_INCLUDE_DIRS}}
    ${{GC_INCLUDE_DIRS}}
)

target_compile_options(runtime PRIVATE
    -fPIC -O3 -fno-plt -march=native
)

set_target_properties(runtime PROPERTIES
    ARCHIVE_OUTPUT_DIRECTORY "{temp_path.as_posix()}/build"
    OUTPUT_NAME "runtime"
)
"""
        (temp_path / "CMakeLists.txt").write_text(cmakelists, encoding="utf-8")

        _run_subprocess(
            ["cmake", "-B", "build", "-S", "."],
            cwd=temp_path,
        )
        _run_subprocess(
            ["cmake", "--build", "build"],
            cwd=temp_path,
        )

        built_lib = temp_path / "build" / "libruntime.a"
        shutil.copy2(built_lib, dest_runtime / "libruntime.a")

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
