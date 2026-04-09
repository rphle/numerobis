"""Build system for compiling runtime C library and generating message headers.

Compiles C sources into two static libraries via CMake:
  - libruntime.a:    all non-graphics runtime sources
  - libgraphics.a:   SDL2-dependent graphics sources (only linked when the
                     graphics stdlib module is imported by the program)

Also generates C headers from message definitions.
"""

import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from numerobis.compiler.cmake import _run_subprocess
from numerobis.compiler.utils import repr_double
from numerobis.exceptions import msgparser

_graphics_pkgconfig_cmake = """\
find_package(PkgConfig REQUIRED)
pkg_check_modules(SDL2     REQUIRED sdl2)
pkg_check_modules(SDL2_TTF REQUIRED SDL2_ttf)
"""


def _is_graphics_source(path: Path) -> bool:
    return path.parent.name == "graphics"


def build_lib():
    t0 = time.time()
    generate_messages()

    script_dir = Path(__file__).parent.resolve()
    runtime_root = script_dir
    dest_runtime = script_dir.parent / "src" / "numerobis" / "runtime"

    if dest_runtime.exists():
        shutil.rmtree(dest_runtime)
    os.makedirs(dest_runtime, exist_ok=True)

    all_sources = [f for f in runtime_root.rglob("*.c") if f.name != "source.c"]
    runtime_sources = [s for s in all_sources if not _is_graphics_source(s)]
    graphics_sources = [s for s in all_sources if _is_graphics_source(s)]

    _build_static_lib(
        name="runtime",
        sources=runtime_sources,
        runtime_root=runtime_root,
        dest=dest_runtime,
        extra_cmake="",
    )

    if graphics_sources:
        _build_static_lib(
            name="graphics",
            sources=graphics_sources,
            runtime_root=runtime_root,
            dest=dest_runtime,
            extra_cmake=_graphics_pkgconfig_cmake,
        )

    for h_file in runtime_root.rglob("*.h"):
        target_path = dest_runtime / h_file.relative_to(runtime_root)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(h_file, target_path)

    print(
        f"Static libraries and headers created at {dest_runtime} ({time.time() - t0:.2f}s)"
    )


def _build_static_lib(
    name: str,
    sources: list[Path],
    runtime_root: Path,
    dest: Path,
    extra_cmake: str,
) -> None:
    """Compile sources into lib{name}.a and copy it to dest."""
    if not sources:
        return

    source_list = "\n    ".join(str(s.as_posix()) for s in sources)

    if name == "graphics":
        include_extras = """\
    ${SDL2_INCLUDE_DIRS}
    ${SDL2_TTF_INCLUDE_DIRS}"""
        compile_extras = """\
    ${SDL2_CFLAGS_OTHER}
    ${SDL2_TTF_CFLAGS_OTHER}"""
    else:
        include_extras = ""
        compile_extras = ""

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        cmakelists = f"""\
cmake_minimum_required(VERSION 3.10)
project(NumerobisLib_{name} C)

find_package(PkgConfig REQUIRED)
pkg_check_modules(GC   REQUIRED bdw-gc)
{extra_cmake}
set(LIB_SOURCES
    {source_list}
)

add_library({name} STATIC ${{LIB_SOURCES}})

target_include_directories({name} PRIVATE
    "{runtime_root.as_posix()}"
    ${{GC_INCLUDE_DIRS}}
{include_extras}
)

target_compile_options({name} PRIVATE
    -fPIC -O3 -fno-plt -march=native
{compile_extras}
)

set_target_properties({name} PROPERTIES
    ARCHIVE_OUTPUT_DIRECTORY "{temp_path.as_posix()}/build"
    OUTPUT_NAME "{name}"
)
"""
        (temp_path / "CMakeLists.txt").write_text(cmakelists, encoding="utf-8")

        _run_subprocess(["cmake", "-B", "build", "-S", "."], cwd=temp_path)
        _run_subprocess(["cmake", "--build", "build"], cwd=temp_path)

        built_lib = temp_path / "build" / f"lib{name}.a"
        shutil.copy2(built_lib, dest / f"lib{name}.a")

    print(f"  lib{name}.a built successfully")


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
