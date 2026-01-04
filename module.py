import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

from analysis.dimchecker import Dimchecker
from classes import CompiledModule, Header, ModuleMeta
from compiler import gcc as gnucc
from compiler.compiler import Compiler
from compiler.linker import Linker
from environment import Namespaces
from exceptions.exceptions import Exceptions
from lexer.lexer import lex
from nodes.ast import Import
from parser.parser import Parser
from typechecker.linking import Link
from typechecker.typechecker import Typechecker

# pre-compiled modules
MODULECACHE: dict[str, CompiledModule] = {}


class Module:
    def __init__(
        self,
        path: str | Path,
        source: Optional[str] = None,
        namespaces: Optional[Namespaces] = None,
        builtins: bool = True,
    ):
        self.meta = ModuleMeta(
            Path(path),
            open(path, "r", encoding="utf-8").read() if source is None else source,
        )
        self.errors = Exceptions(module=self.meta)
        self.builtins = builtins

        self.namespaces = Namespaces()
        if namespaces is not None:
            self.namespaces.update(namespaces)

        self.header: Header = Header()
        self.program: list[Link] = []
        self.imports: list[str] = []

        self.linker: Optional[Linker] = None
        self.compiled: CompiledModule

    def load(self) -> CompiledModule:
        path = str(self.meta.path)
        if path in MODULECACHE:
            if MODULECACHE[path].namespaces is not None:
                self.namespaces.update(MODULECACHE[path].namespaces)  # type: ignore
            return MODULECACHE[path]
        self.parse()
        self.typecheck()
        self.compile()
        return self.compiled

    def parse(self):
        lexed = lex(self.meta.source, module=self.meta)
        parser = Parser(lexed, module=self.meta)
        self.ast = parser.start()
        self.header = parser.header
        del parser

        self.resolve_imports()

    def resolve_imports(self):
        if self.builtins:
            builtins_mod = Module("stdlib/builtins.und", builtins=False)
            builtins_mod.load()
            self.namespaces.update(builtins_mod.namespaces)

        if len(self.ast) == 0:
            return

        resolver = ModuleResolver(search_paths=[self.meta.path.parent.resolve()])
        for i, node in enumerate(self.header.imports):
            try:
                self.imports.append(
                    str(resolver.resolve(node.module.name.removeprefix("@")))
                )
            except FileNotFoundError:
                self.errors.throw(802, module=node.module.name, loc=node.loc)

        modules = [Module(path) for path in self.imports]
        for module, node in zip(modules, self.header.imports):
            module.load()

            if isinstance(node, Import):
                self.namespaces.write("imports", node.module.name, module.namespaces)
            else:
                if node.names is None:
                    # import *
                    self.namespaces.update(module.namespaces)
                else:
                    for name in node.names:
                        if name.name.startswith("@"):
                            # unit/dimension
                            n = name.name.removeprefix("@")
                            typ = (
                                "dimensions"
                                if n in module.namespaces("dimensions")
                                else "units"
                            )
                            try:
                                self.namespaces.write(typ, n, module.namespaces(typ)[n])
                            except KeyError:
                                self.errors.throw(
                                    803, name=name.name.removeprefix("@"), loc=name.loc
                                )
                        else:
                            # import name
                            try:
                                self.namespaces.write(
                                    "names",
                                    name.name,
                                    module.namespaces("names")[name.name],
                                )
                            except KeyError:
                                help = [
                                    ns
                                    for ns in ("units", "dimensions")
                                    if name.name in module.namespaces(ns)
                                ]
                                self.errors.throw(
                                    804,
                                    name=name.name,
                                    help=f"the module does export a {help[0][:-1]} named '{name.name}', did you forget the '@' prefix?"
                                    if help
                                    else "",
                                    loc=name.loc,
                                )
                    self.namespaces.write(
                        "imports", node.module.name, module.namespaces
                    )

        if self.builtins:
            self.imports.append("stdlib/builtins.und")

    def dimcheck(self):
        dc = Dimchecker(
            module=self.meta, namespaces=self.namespaces, header=self.header
        )
        dc.start()
        self.namespaces = dc.env

    def typecheck(self):
        self.dimcheck()
        ts = Typechecker(self.ast, module=self.meta, namespaces=self.namespaces)
        ts.start()
        self.program = ts.program

    def compile(self):
        compiler = Compiler(
            self.program,
            module=self.meta,
            namespaces=self.namespaces,
            header=self.header,
            imports=self.imports,
        )
        self.compiled = compiler.start()

        MODULECACHE[str(self.meta.path)] = self.compiled
        MODULECACHE[str(self.meta.path)].namespaces = self.namespaces

    def link(self, format: bool = False):
        self.linker = Linker(MODULECACHE, main=self.meta.path)
        self.linker.link(format=format)

    def gcc(self):
        if self.linker is None:
            raise ValueError("Module not linked")
        self.linker.gcc()

    def run(self, path: str = "output/output"):
        try:
            proc = gnucc.run(path=path)
            print(proc.stdout)
            if proc.returncode != 0:
                print(proc.stderr, file=sys.stderr)
                sys.exit(proc.returncode)
        except subprocess.CalledProcessError as e:
            self.errors.throw(201, command=" ".join(map(str, e.cmd)), help=e.stderr)


class ModuleResolver:
    def __init__(
        self,
        stdlib_path: Optional[str | Path] = None,
        search_paths: list[str | Path] = [],
    ):
        self.stdlib_path = (
            Path(stdlib_path) if stdlib_path else Path(__file__).parent / "stdlib"
        )
        self.search_paths = [Path(p) for p in search_paths]

    @lru_cache(maxsize=128)
    def resolve(self, name: str) -> Path:
        """Resolve a module name to a file path."""
        file = name.replace(".", "/") + ".und"

        # Check stdlib first
        if (path := self.stdlib_path / file).is_file():
            return path.resolve()

        # Check search paths
        for search_dir in set(self.search_paths):
            if (path := search_dir / file).is_file():
                return path.resolve()

        raise FileNotFoundError(f"Module '{name}' not found")
