"""CMake compiler integration for generating native executables from C code."""

import shutil
import subprocess
import tempfile
from importlib import resources
from pathlib import Path
from typing import Optional

from ..classes import CompiledUnits, ModuleMeta
from .utils import repr_double


def _prepare_units_h(units: CompiledUnits) -> str:
    out = f"""#ifndef NUMEROBIS_UNITS_DEF_H
    #define NUMEROBIS_UNITS_DEF_H

    #include <stdint.h>
    #include <math.h>

    typedef enum {{
        {",".join(["DUMMY93CF"] + list(units.units.keys()))}
    }} UnitId;

    static inline double logn(double x, double b);

    double unit_id_eval(uint16_t id, double x);
    double unit_id_eval_normal(uint16_t id, double x);
    double base_unit(uint16_t id, double x);
    double is_logarithmic(uint16_t id);

    #endif
    """

    return out


def _prepare_source_c(
    modules: list[ModuleMeta],
    units_h: str,
    units: CompiledUnits,
):
    arrays, structs, entries = [], [], []

    for i, mod in enumerate(modules):
        src_lines = mod.source.splitlines()
        c_lines = ", ".join(repr_double(line) for line in src_lines)
        path_str = repr_double(str(mod.path))

        arrays.append(f"static const char *lines_{i}[] = {{ {c_lines} }};")
        structs.append(
            f"static NumerobisProgram mod_{i} = {{ {path_str}, {len(src_lines)}, lines_{i} }};"
        )
        entries.append(f"shput(NUMEROBIS_MODULE_REGISTRY, {path_str}, &mod_{i});")

    unit_names = "\n".join(
        f'    [{uid}] = "{name}",' for uid, name in units.names.items()
    )

    source = f"""#include <math.h>
    #include <stdbool.h>
    #include <stdint.h>
    #include <numerobis/libs/stb_ds.h>
    #include "{units_h}"

    typedef struct {{
        const char *path;
        const int n_lines;
        const char **source;
    }} NumerobisProgram;

    typedef struct {{ char *key; NumerobisProgram *value; }} ModuleEntry;
    extern ModuleEntry *NUMEROBIS_MODULE_REGISTRY;

    {chr(10).join(arrays)}
    {chr(10).join(structs)}

    static inline double logn(double b, double x) {{return log(x) / log(b);}}

    double unit_id_eval(uint16_t id, double x) {{
        switch ((UnitId)id) {{
            {"\n".join(f"case {n}: return {expr};" for n, expr in units.inverted.items())}
            default: return 1;
        }}
    }}

    double unit_id_eval_normal(uint16_t id, double x) {{
        switch ((UnitId)id) {{
            {"\n".join(f"case {n}: return {expr};" for n, expr in units.units.items())}
            default: return 1;
        }}
    }}

    double base_unit(uint16_t id, double x) {{
        switch ((UnitId)id) {{
            {"\n".join(f"case {n}: return {expr};" for n, expr in units.bases.items() if expr)}
            default: return 1;
        }}
    }}

    double is_logarithmic(uint16_t id) {{
        switch ((UnitId)id) {{
            {"\n".join(f"case {n}: return true;" for n in units.logarithmic)}
            default: return false;
        }}
    }}

    const char *NUMEROBIS_UNIT_NAMES[] = {{
    {unit_names}
    }};

    __attribute__((constructor))
    void u_init_module_registry() {{
        {chr(10).join(entries)}
    }}
    """
    return source


def _run_subprocess(cmd: list[str], cwd: Path):
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )

    if proc.returncode != 0:
        print(f"\n--- BUILD FAILED: {' '.join(cmd)} ---")
        print(f"STDOUT:\n{proc.stdout}")
        print(f"STDERR:\n{proc.stderr}")
        raise SystemExit(1)
    return proc


def compile(
    code: str,
    modules: list[ModuleMeta],
    units: CompiledUnits,
    output: str | Path = "output/output",
    flags: set[str] = set(),
    cc: str = "gcc",
    linker: Optional[str] = None,
    use_graphics: bool = False,
    use_ccache: bool = False,
):
    output_path = Path(output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    units_h = _prepare_units_h(units)
    source_c = _prepare_source_c(modules, "units.h", units)
    main_c = f'#include "units.h"\n{code}'

    combined_flags = " ".join({"-O3", "-fno-plt", "-march=native"} | flags)

    with resources.as_file(resources.files("numerobis")) as base_path:
        runtime_path = base_path / "runtime"
        runtime_lib = runtime_path / "libruntime.a"
        graphics_lib = runtime_path / "libgraphics.a"

        gc_path = runtime_path / "numerobis" / "libs" / "bdwgc"
        gc_lib_static = gc_path / "lib" / "libgc.a"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            (temp_path / "units.h").write_text(units_h, encoding="utf-8")
            (temp_path / "source.c").write_text(source_c, encoding="utf-8")
            (temp_path / "main.c").write_text(main_c, encoding="utf-8")

            if use_graphics:
                graphics_pkgconfig = """\
pkg_check_modules(SDL2     REQUIRED sdl2)
pkg_check_modules(SDL2_TTF REQUIRED SDL2_ttf)
"""
                graphics_include_dirs = """\
    ${SDL2_INCLUDE_DIRS}
    ${SDL2_TTF_INCLUDE_DIRS}"""
                graphics_link_dirs = """\
    ${SDL2_LIBRARY_DIRS}
    ${SDL2_TTF_LIBRARY_DIRS}"""
                graphics_libs = f"""\
    "-Wl,--whole-archive"
    "{graphics_lib.as_posix()}"
    "-Wl,--no-whole-archive"
    ${{SDL2_LIBRARIES}}
    ${{SDL2_TTF_LIBRARIES}}"""
            else:
                graphics_pkgconfig = ""
                graphics_include_dirs = ""
                graphics_link_dirs = ""
                graphics_libs = ""

            cmakelists = f"""\
cmake_minimum_required(VERSION 3.10)
project(NumerobisNative C)

find_package(PkgConfig REQUIRED)
{graphics_pkgconfig}
add_executable(numerobis_bin main.c source.c)

target_include_directories(numerobis_bin PRIVATE
{graphics_include_dirs}
    "{runtime_path.as_posix()}"
)

target_link_directories(numerobis_bin PRIVATE
{graphics_link_dirs}
)

target_compile_options(numerobis_bin PRIVATE {combined_flags})

target_link_libraries(numerobis_bin PRIVATE
    "-Wl,--whole-archive"
    "{runtime_lib.as_posix()}"
    "-Wl,--no-whole-archive"
{graphics_libs}
    "{gc_lib_static.as_posix()}"
    m
    pthread
    dl
)
"""
            (temp_path / "CMakeLists.txt").write_text(cmakelists, encoding="utf-8")

            cmake_config = [
                "cmake",
                "-B",
                "build",
                "-S",
                ".",
                f"-DCMAKE_C_COMPILER={cc}",
                "-DCMAKE_C_COMPILER_LAUNCHER=ccache" if use_ccache else "",
                f"-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld={linker}" if linker else "",
            ]

            _run_subprocess(cmake_config, cwd=temp_path)

            build_proc = _run_subprocess(["cmake", "--build", "build"], cwd=temp_path)

            built_binary = temp_path / "build" / "numerobis_bin"
            shutil.copy2(built_binary, output_path)

            return build_proc


def run(path: str | Path = "output/output", capture_output=True):
    return subprocess.run(
        [str(path)],
        check=False,
        text=True,
        capture_output=capture_output,
        encoding="utf-8",
        errors="replace",
    )
