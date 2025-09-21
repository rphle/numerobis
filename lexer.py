import sys

import lex as plylex
from classes import Location, Token

reserved = ("IF", "THEN", "ELSE", "TRUE", "FALSE", "OR", "AND", "NOT", "XOR", "UNIT")

tokens = reserved + (
    # Literals (identifier, integer, float, string, boolean)
    "ID",
    "NUMBER",
    "STRING",
    # Operators (+,-,*,/,%,^,or,and,xor, !, <, <=, >, >=, ==, !=)
    "PLUS",
    "MINUS",
    "TIMES",
    "DIVIDE",
    "INTDIVIDE",
    "MOD",
    "POWER",
    "LT",
    "LE",
    "GT",
    "GE",
    "EQ",
    "NE",
    "CONVERSION",
    # Assignment (=)
    "ASSIGN",
    # Delimiters ( ) [ ] { } , . ; :
    "LPAREN",
    "RPAREN",
    "LBRACKET",
    "RBRACKET",
    "LBRACE",
    "RBRACE",
    "COMMA",
    "PERIOD",
    "SEMICOLON",
    "COLON",
    "AMPERSAND",
    # Hacks
    "WHITESPACE",
)


# Newlines
def t_NEWLINE(t):
    r"\n+"
    t.lexer.lineno += t.value.count("\n")
    return t


# Operators
t_PLUS = r"\+"
t_MINUS = r"-"
t_TIMES = r"\*"
t_DIVIDE = r"/"
t_INTDIVIDE = r"//"
t_MOD = r"%"
t_POWER = r"\^"
t_OR = r"or"
t_AND = r"and"
t_NOT = r"not|!"
t_XOR = r"xor"
t_LT = r"<"
t_GT = r">"
t_LE = r"<="
t_GE = r">="
t_EQ = r"=="
t_NE = r"!="
t_CONVERSION = r"->"

# Assignment operators
t_ASSIGN = r"="

# Delimiters
t_LPAREN = r"\("
t_RPAREN = r"\)"
t_LBRACKET = r"\["
t_RBRACKET = r"\]"
t_LBRACE = r"\{"
t_RBRACE = r"\}"
t_COMMA = r","
t_PERIOD = r"\."
t_SEMICOLON = r";"
t_COLON = r":"
t_AMPERSAND = r"&"

t_WHITESPACE = r"\s+"


# Identifiers and reserved words
reserved_map = {}
for r in reserved:
    reserved_map[r.lower()] = r


def t_ID(t):
    r"(?:[^\W\d]|°)[\w°]*"
    t.type = reserved_map.get(t.value, "ID")
    return t


# Number literal
t_NUMBER = r"\d+(_\d+)* (\.\d+(_\d+)*)? ([eE][+-]? \d+(_\d+)* (\.\d+(_\d+)*)?)?"
# String literal
t_STRING = r"\"([^\\\n]|(\\.))*?\""


# Comments
def t_comment(t):
    r"\#.*"
    t.lexer.lineno += t.value.count("\n")


def t_error(t):
    print("Illegal character %s" % repr(t.value[0]))
    print(t)
    sys.exit(1)


lexer = plylex.lex()


def lex(source: str) -> list[Token]:
    output: list[Token] = []
    lexer.input(source)

    last_newline_pos = [0, 0]
    while True:
        tok = lexer.token()
        if not tok:
            break

        if tok.type == "NEWLINE":
            last_newline_pos.append(tok.lexpos + len(tok.value))
            last_newline_pos.pop(0)

        token = Token(
            type=tok.type if tok.type != "NEWLINE" else "WHITESPACE",
            value=tok.value,
            loc=Location(
                line=tok.lineno,
                col=tok.lexpos - last_newline_pos[-1],
                start=tok.lexpos,
                end=tok.lexpos + len(tok.value),
            ),
        )
        print(token)
        output.append(token)

    return output
