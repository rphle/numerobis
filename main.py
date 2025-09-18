from parser import parse

from lexer import lex

source = open("test.und", "r").read()
lexed = lex(source)
print("=" * 80)
parse(lexed)
