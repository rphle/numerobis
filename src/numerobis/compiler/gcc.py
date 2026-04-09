"""GCC compiler integration for generating native executables from C code."""

import os
import subprocess
import tempfile
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Optional

from ..classes import CompiledUnits, ModuleMeta
from .utils import repr_double


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


def _prepare_source_c(modules: list[ModuleMeta], units_h: str, units: CompiledUnits):
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
    gc_cflags, gc_libs = _pkg("bdw-gc")

    if use_graphics:
        sdl2_cflags, sdl2_libs = _pkg("sdl2")
        sdl2_ttf_cflags, sdl2_ttf_libs = _pkg("SDL2_ttf")
    else:
        sdl2_cflags = sdl2_libs = sdl2_ttf_cflags = sdl2_ttf_libs = []

    units_h = _prepare_units_h(units)

    tmp_units = tempfile.NamedTemporaryFile(delete=False, suffix=".h")
    tmp_units.write(units_h.encode("utf-8"))
    tmp_units.close()

    source = _prepare_source_c(modules, tmp_units.name, units)

    tmp_source = tempfile.NamedTemporaryFile(delete=False, suffix=".c")
    tmp_source.write(source.encode("utf-8"))
    tmp_source.close()

    code = f'#include "{tmp_units.name}"\n{code}'

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".c")
    tmp.write(code.encode("utf-8"))
    tmp.close()

    flags = {"-O3", "-fno-plt", "-march=native"} | flags

    with resources.as_file(resources.files("numerobis")) as base_path:
        runtime_path = base_path / "runtime"
        graphics_libs = (
            [
                "-Wl,--whole-archive",
                str(runtime_path / "libgraphics.a"),
                "-Wl,--no-whole-archive",
            ]
            + sdl2_libs
            + sdl2_ttf_libs
            if use_graphics
            else []
        )
        cmd = (
            (["ccache"] if use_ccache else [])
            + [cc]
            + ([f"-fuse-ld={linker}"] if linker else [])
            + ["-pipe"]
            + [tmp.name, tmp_source.name]
            + ["-o", str(output)]
            + [f"-I{runtime_path}"]
            + gc_cflags
            + sdl2_cflags
            + sdl2_ttf_cflags
            + [
                "-Wl,--whole-archive",
                str(runtime_path / "libruntime.a"),
                "-Wl,--no-whole-archive",
            ]
            + graphics_libs
            + gc_libs
            + ["-lm"]
            + list(flags)
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
        os.unlink(tmp_units.name)


def run(path: str | Path = "output/output", capture_output=True):
    return subprocess.run(
        [str(path)],
        check=False,
        text=True,
        capture_output=capture_output,
        encoding="utf-8",
        errors="replace",
    )
