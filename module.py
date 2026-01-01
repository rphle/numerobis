import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Optional

import typechecker.declare as declare
from analysis.dimchecker import Dimchecker
from classes import Header, ModuleMeta
from compiler import gcc as gnucc
from compiler.compiler import Compiler
from environment import Namespaces
from exceptions.exceptions import Exceptions
from lexer.lexer import lex
from nodes.ast import Import
from parser.parser import Parser
from typechecker.linking import Link
from typechecker.typechecker import Typechecker


class Module:
    def __init__(
        self,
        path: str | Path,
        source: Optional[str] = None,
        namespaces: Optional[Namespaces] = None,
    ):
        self.meta = ModuleMeta(
            Path(path),
            open(path, "r", encoding="utf-8").read() if source is None else source,
        )
        self.errors = Exceptions(module=self.meta)

        self.namespaces = Namespaces(names=declare.names.copy())
        if namespaces is not None:
            self.namespaces.update(namespaces)

        self.header: Header = Header()
        self.program: list[Link] = []

    def parse(self):
        lexed = lex(self.meta.source, module=self.meta)
        parser = Parser(lexed, module=self.meta)
        self.ast = parser.start()
        self.header = parser.header
        del parser

        self.resolve_imports()

    def resolve_imports(self):
        if len(self.ast) == 0:
            return

        resolver = ModuleResolver(search_paths=[self.meta.path.parent.resolve()])
        paths = []
        for i, node in enumerate(self.header.imports):
            try:
                paths.append(resolver.resolve(node.module.name.removeprefix("@")))
            except FileNotFoundError:
                self.errors.throw(802, module=node.module.name, loc=node.loc)

        modules = [Module(path) for path in paths]
        for module, node in zip(modules, self.header.imports):
            module.parse()
            module.typecheck()
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
        self.compiler = Compiler(
            self.program, module=self.meta, namespaces=self.namespaces
        )
        self.compiler.start()

    def gcc(self):
        self.compiler.gcc()

    def run(self, path: str = "output/output"):
        try:
            print(gnucc.run(path=path).stdout)
        except subprocess.CalledProcessError as e:
            self.errors.throw(901, command=" ".join(map(str, e.cmd)), help=e.stderr)


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
