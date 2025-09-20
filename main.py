from parser import Parser

import rich

from lexer import lex

source = open("test.und", "r").read()

lexed = lex(source)
print("=" * 80)
parser = Parser(lexed)
rich.print(parser.start())
