from parser.parser import Parser

from classes import ModuleMeta
from dimchecker import Dimchecker
from lexer import lex


class Module:
    def __init__(self, path: str):
        self.meta = ModuleMeta(path, open(path, "r", encoding="utf-8").read())

    def parse(self):
        lexed = lex(self.meta.source, module=self.meta)
        parser = Parser(lexed, module=self.meta)
        self.ast = parser.start()

    def dimcheck(self):
        tc = Dimchecker(self.ast, module=self.meta)
        tc.start()
