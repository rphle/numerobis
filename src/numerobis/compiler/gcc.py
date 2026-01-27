import os
import subprocess
import tempfile
from functools import lru_cache
from importlib import resources
from pathlib import Path

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
    #include <glib.h>

    typedef enum {{
        {",".join(["DUMMY93CF"] + list(units.units.keys()))}
    }} UnitId;

    static inline gdouble logn(gdouble x, gdouble b);

    gdouble unit_id_eval(uint16_t id, gdouble x);
    gdouble unit_id_eval_normal(uint16_t id, gdouble x);
    gdouble base_unit(uint16_t id, gdouble x);
    gdouble is_logarithmic(uint16_t id);

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
        entries.append(
            f"g_hash_table_insert(NUMEROBIS_MODULE_REGISTRY, (gpointer){path_str}, &mod_{i});"
        )

    source = f"""#include <glib.h>
    #include <math.h>
    #include <stdbool.h>
    #include "{units_h}"

    typedef struct {{
        const gchar *path;
        const int n_lines;
        const gchar **source;
    }} NumerobisProgram;

    extern GHashTable *NUMEROBIS_MODULE_REGISTRY;

    {chr(10).join(arrays)}
    {chr(10).join(structs)}

    static inline gdouble logn(gdouble b, gdouble x) {{return log(x) / log(b);}}

    gdouble unit_id_eval(uint16_t id, gdouble x) {{
        switch ((UnitId)id) {{
            {"\n".join(f"case {n}: return {expr};" for n, expr in units.inverted.items())}
            default: return 1;
        }}
    }}

    gdouble unit_id_eval_normal(uint16_t id, gdouble x) {{
        switch ((UnitId)id) {{
            {"\n".join(f"case {n}: return {expr};" for n, expr in units.units.items())}
            default: return 1;
        }}
    }}

    gdouble base_unit(uint16_t id, gdouble x) {{
        switch ((UnitId)id) {{
            {"\n".join(f"case {n}: return {expr};" for n, expr in units.bases.items() if expr)}
            default: return 1;
        }}
    }}

    gdouble is_logarithmic(uint16_t id) {{
        switch ((UnitId)id) {{
            {"\n".join(f"case {n}: return true;" for n in units.logarithmic)}
            default: return false;
        }}
    }}

    __attribute__((constructor))
    void u_init_module_registry() {{
        if (NUMEROBIS_MODULE_REGISTRY == NULL) {{
            NUMEROBIS_MODULE_REGISTRY = g_hash_table_new(g_str_hash, g_str_equal);
        }}
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
    cache: bool = False,
    cc: str = "gcc",
):
    glib_cflags, glib_libs = _pkg("glib-2.0")
    gc_cflags, gc_libs = _pkg("bdw-gc")

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

    flags = {"-O0", "-g"} | flags

    with resources.as_file(
        resources.files("numerobis.runtime") / "libruntime.a"
    ) as runtime_path:
        cmd = (
            (["ccache", "mold", "-run"] if cache else [])
            + [cc]
            + ["-pipe"]
            + [tmp.name, tmp_source.name]
            + ["-o", str(output)]
            + ["-Iruntime"]
            + glib_cflags
            + gc_cflags
            + [
                "-Wl,--whole-archive",
                str(runtime_path),
                "-Wl,--no-whole-archive",
            ]
            + glib_libs
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
