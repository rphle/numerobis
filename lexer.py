import sys

import lex as plylex
from classes import Location, Token

reserved = ("IF", "THEN", "ELSE", "TRUE", "FALSE", "OR", "AND", "NOT", "XOR")

tokens = reserved + (
    # Literals (identifier, integer, float, string, boolean)
    "ID",
    "INTEGER",
    "FLOAT",
    "STRING",
    # Operators (+,-,*,/,%,^,or,and,xor, !, <, <=, >, >=, ==, !=)
    "PLUS",
    "MINUS",
    "TIMES",
    "DIVIDE",
    "MOD",
    "POWER",
    "LT",
    "LE",
    "GT",
    "GE",
    "EQ",
    "NE",
    # Assignment (=)
    "EQUALS",
    # Delimiters ( ) [ ] { } , . ; :
    "LPAREN",
    "RPAREN",
    "LBRACKET",
    "RBRACKET",
    "LBRACE",
    "RBRACE",
    "COMMA",
    "PERIOD",
    "SEMI",
    "COLON",
    # Hacks
    "INVALID_E",
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
t_MOD = r"%"
t_POWER = r"\*\*"
t_OR = r"or"
t_AND = r"and"
t_NOT = r"not"
t_XOR = r"xor"
t_LT = r"<"
t_GT = r">"
t_LE = r"<="
t_GE = r">="
t_EQ = r"=="
t_NE = r"!="

# Assignment operators
t_EQUALS = r"="

# Delimiters
t_LPAREN = r"\("
t_RPAREN = r"\)"
t_LBRACKET = r"\["
t_RBRACKET = r"\]"
t_LBRACE = r"\{"
t_RBRACE = r"\}"
t_COMMA = r","
t_PERIOD = r"\."
t_SEMI = r";"
t_COLON = r":"


# Hacks (wow, regex is ugly)
def t_INVALID_E(t):
    r"((\d+(_\d+)*)?\.\d+(_\d+)* | \d+(_\d+)*) [eE][+-]? (\d+(_\d+)*)? \. \d+(_\d+)*"
    print(t)
    sys.exit(1)


t_WHITESPACE = r"\s+"


# Identifiers and reserved words
reserved_map = {}
for r in reserved:
    reserved_map[r.lower()] = r


def t_ID(t):
    r"[A-Za-z_][\w_]*"
    t.type = reserved_map.get(t.value, "ID")
    return t


# Integer literal
t_INTEGER = r"\d+(_\d+)*([eE][+-]?\d+(_\d+)*)?(?!\.)"
# Floating literal
t_FLOAT = r"(\d+(_\d+)*)?\.\d+(_\d+)*([eE][+-]?\d+(_\d+)*)?"
# String literal
t_STRING = r"\"([^\\\n]|(\\.))*?\""


# Comments
def t_comment(t):
    r"/\*(.|\n)*?\*/"
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

    output.append(
        Token(
            type="EOF",
            value="",
            loc=Location(),
        )
    )

    return output
