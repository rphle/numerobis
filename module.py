from parser.parser import Parser

from typechecker import Namespaces, Typechecker

from classes import ModuleMeta
from lexer import lex


class Module:
    def __init__(self, path: str):
        self.meta = ModuleMeta(path, open(path, "r", encoding="utf-8").read())
        self._dimchecker = None

    def parse(self):
        lexed = lex(self.meta.source, module=self.meta)
        parser = Parser(lexed, module=self.meta)
        self.ast = parser.start()

    def dimcheck(self, namespaces: Namespaces | None = None):
        self._dimchecker = Typechecker(
            self.ast, module=self.meta, namespaces=namespaces
        )
        self._dimchecker.start()

        return self._dimchecker
