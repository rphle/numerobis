from functools import lru_cache
from pathlib import Path
from typing import Optional

import declare
from astnodes import FromImport, Import
from classes import ModuleMeta
from environment import Namespaces
from exceptions import Exceptions, uImportError, uModuleNotFound, uSyntaxError
from lexer.lexer import lex
from parser.parser import Parser
from typechecker.typechecker import Typechecker


class Module:
    def __init__(self, path: str | Path):
        self.meta = ModuleMeta(Path(path), open(path, "r", encoding="utf-8").read())
        self.errors = Exceptions(module=self.meta)

        self.namespaces = Namespaces(names=declare.names.copy())

    def process(self):
        self.parse()
        self.resolve_imports()
        self.typecheck()

    def parse(self):
        lexed = lex(self.meta.source, module=self.meta)
        parser = Parser(lexed, module=self.meta)
        self.ast = parser.start()

    def resolve_imports(self):
        if len(self.ast) == 0:
            return

        # Find and verifiy import nodes first
        nodes: list[Import | FromImport] = []
        while len(self.ast) > 0 and isinstance(
            (node := self.ast[0]), (Import, FromImport)
        ):
            nodes.append(self.ast.pop(0))  # type: ignore

        if node := next(
            (node for node in self.ast if isinstance(node, (Import, FromImport))), None
        ):
            self.errors.throw(
                exception=uSyntaxError,
                message="import declarations may only appear at top level of a module",
                loc=node.loc,
            )

        resolver = ModuleResolver(search_paths=[self.meta.path.parent.resolve()])
        paths = []
        for i, node in enumerate(nodes):
            try:
                paths.append(resolver.resolve(node.module.name.removeprefix("@")))
            except FileNotFoundError:
                self.errors.throw(
                    exception=uModuleNotFound,
                    message=f"failed to resolve import: module '{node.module.name}' does not exist",
                    loc=node.loc,
                )

        modules = [Module(path) for path in paths]
        for module, node in zip(modules, nodes):
            module.process()
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
                                    exception=uImportError,
                                    message=f"failed to resolve import: unit or dimension '{name.name.removeprefix('@')}' does not exist",
                                    loc=name.loc,
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
                                    exception=uImportError,
                                    help=f"the module does export a {help[0][:-1]} named '{name.name}', did you forget the '@' prefix?"
                                    if help
                                    else "",
                                    message=f"failed to resolve import: name '{name.name}' does not exist",
                                    loc=name.loc,
                                )
                    self.namespaces.write(
                        "imports", node.module.name, module.namespaces
                    )

    def typecheck(self):
        ts = Typechecker(self.ast, module=self.meta, namespaces=self.namespaces)
        ts.start()


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
