from parser.parser import Parser
from pathlib import Path

from astnodes import FromImport, Import
from classes import ModuleMeta
from exceptions import Exceptions, uImportError, uModuleNotFound, uSyntaxError
from lexer import lex
from module_resolver import ModuleResolver
from typechecker import Namespaces, Typechecker


class Module:
    def __init__(self, path: str):
        self.meta = ModuleMeta(Path(path), open(path, "r", encoding="utf-8").read())
        self.errors = Exceptions(module=self.meta)

        self.namespaces = Namespaces()

    def process(self):
        self.parse()
        self.resolve_imports()
        self.typecheck()

    def parse(self):
        lexed = lex(self.meta.source, module=self.meta)
        parser = Parser(lexed, module=self.meta)
        self.ast = parser.start()

    def resolve_imports(self):
        # Find and verifiy import nodes first
        nodes: list[Import | FromImport] = []
        while isinstance((node := self.ast[0]), (Import, FromImport)):
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
                paths.append(resolver.resolve(node.module.name))
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
                self.namespaces.imports[node.module.name] = module.namespaces
            else:
                if node.names is None:
                    # import *
                    self.namespaces.update(module.namespaces)
                else:
                    for name in node.names:
                        if name.name.startswith("@"):
                            # unit/dimension
                            n = name.name[1:]
                            typ = (
                                "dimensions"
                                if n in module.namespaces.dimensions
                                else "units"
                            )
                            getattr(self.namespaces, typ)[n] = getattr(
                                module.namespaces, typ
                            )[n]
                        else:
                            # import name
                            try:
                                self.namespaces.names[name.name] = (
                                    module.namespaces.names[name.name]
                                )
                            except KeyError:
                                self.errors.throw(
                                    exception=uImportError,
                                    message=f"failed to resolve import: name '{name.name}' does not exist",
                                    loc=name.loc,
                                )
                    self.namespaces.imports[node.module.name] = module.namespaces

    def typecheck(self):
        ts = Typechecker(self.ast, module=self.meta, namespaces=self.namespaces)
        ts.start()
