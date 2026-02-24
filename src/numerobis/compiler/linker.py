"""Linker for combining compiled modules."""

import subprocess
from functools import lru_cache
from pathlib import Path

import rich
import rich.syntax

from ..classes import CompiledModule, CompiledUnits
from ..exceptions.exceptions import Exceptions
from . import gcc as gnucc
from .tstr import tstr
from .utils import module_uid


class Linker:
    def __init__(self, modules: dict[str, CompiledModule], main: Path):
        self.modules = modules
        self.main = main
        self.errors = Exceptions(module=modules[str(self.main)].meta)

        self.include = set()
        self.order: list[list[str]] = [[], []]
        self.linked: str

        self.root = next(
            (
                p
                for p in (main.resolve().parent, *main.resolve().parents)
                if p.name == main.parts[0]
            ),
            Path("."),
        )

    def process_module(self, module: CompiledModule):
        if str(module.meta.path) in self.order[0]:
            return

        self.include.update(module.include)

        for dependency in module.imports:
            self.process_module(self.modules[dependency])

        self.order[0].append(str(module.meta.path))
        self.order[1].append(module_uid(module.meta.path))

    def link(self, print_: bool = False, format: bool = False):
        self.process_module(self.modules[str(self.main)])

        code = tstr("""$include

                    $typedefs

                    enum NumerobisFile {
                        $filehashes
                    };

                    const char* NUMEROBIS__FILES__[] = {
                        $filenames
                    };

                    extern void u_init_module_registry(void);

                    $functions

                    int main() {
                        u_init_module_registry();

                        $output
                        return 0;
                    }""")

        code["include"] = "\n".join([f"#include <{lib}.h>" for lib in self.include])
        code["filehashes"] = ", ".join([f"__FILE__{uid}" for uid in self.order[1]])
        code["filenames"] = ", ".join(
            [f'"{self._path(file)}"' for file in self.order[0]]
        )

        output = []
        functions = []
        typedefs = []
        for file, uid in zip(*self.order):
            module = self.modules[file]
            module.meta.path = Path(self._path(file))
            output.append(
                f"/* {self._path(file)} */\nNUMEROBIS__FILE__ = __FILE__{uid};\n{module.code}\n"
            )
            functions.extend(module.functions)
            typedefs.extend(module.typedefs)

        self.order[0] = [self._path(file) for file in self.order[0]]

        code["output"] = "\n\n".join(output)
        code["functions"] = "\n\n".join(functions)
        code["typedefs"] = "\n\n".join(typedefs)

        code = str(code).strip()
        if format:
            code = subprocess.run(
                ["clang-format"], input=code, text=True, capture_output=True
            ).stdout

        if print_:
            if not format:
                rich.print(code)
            else:
                rich.print(
                    rich.syntax.Syntax(
                        code,
                        "C",
                        theme="monokai",
                        line_numbers=False,
                        background_color="#000000",
                    )
                )
        self.linked = code
        return code

    @lru_cache(maxsize=None)
    def _path(self, p: str | Path) -> str:
        """Get path relative to main module's directory"""
        try:
            return str(Path(p).resolve().relative_to(self.root.resolve()))
        except ValueError:
            return str(p)

    def gcc(
        self,
        output_path: str = "output/output",
        flags: set[str] = set(),
        cache: bool = False,
        cc: str = "gcc",
    ):
        units = CompiledUnits(
            units={
                k: v for m in self.modules.values() for k, v in m.units.units.items()
            },
            inverted={
                k: v for m in self.modules.values() for k, v in m.units.inverted.items()
            },
            bases={
                k: v for m in self.modules.values() for k, v in m.units.bases.items()
            },
            logarithmic={n for m in self.modules.values() for n in m.units.logarithmic},
        )
        try:
            gnucc.compile(
                self.linked,
                modules=[
                    m.meta
                    for m in self.modules.values()
                    if str(m.meta.path) in self.order[0]
                ],
                units=units,
                output=output_path,
                flags=flags,
                cache=cache,
                cc=cc,
            )
        except subprocess.CalledProcessError as e:
            self.errors.throw(201, command=" ".join(map(str, e.cmd)), help=e.stderr)
