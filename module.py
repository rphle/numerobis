from parser.parser import Parser

from classes import ModuleMeta
from lexer import lex
from typechecker import Typechecker


class Module:
    def __init__(self, path: str):
        self.meta = ModuleMeta(path, open(path, "r", encoding="utf-8").read())

    def parse(self):
        lexed = lex(self.meta.source, module=self.meta)
        parser = Parser(lexed, module=self.meta)
        self.ast = parser.start()

    def typecheck(self):
        tc = Typechecker(self.ast, module=self.meta)
        tc.start()
