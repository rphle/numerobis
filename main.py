from parser import Parser

from lexer import lex

source = open("test.und", "r").read()
source = "1+1*2-2/6"
lexed = lex(source)
print("=" * 80)
parser = Parser(lexed)
print(parser.start())
