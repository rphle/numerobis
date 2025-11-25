import lexer.plylex as plylex
from astnodes import Location, Token
from classes import ModuleMeta
from exceptions.exceptions import Exceptions


class LexTokens:
    reserved = (
        "IF",
        "THEN",
        "ELSE",
        "FOR",
        "IN",
        "DO",
        "WHILE",
        "TRUE",
        "FALSE",
        "OR",
        "AND",
        "NOT",
        "XOR",
        "UNIT",
        "DIMENSION",
        "BREAK",
        "CONTINUE",
        "RETURN",
        "IMPORT",
        "FROM",
    )

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
        "RANGE",
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
        "AT",
        "BANG",
        # Hacks
        "WHITESPACE",
    )

    # Operators
    t_PLUS = r"\+"
    t_MINUS = r"-"
    t_TIMES = r"\*"
    t_DIVIDE = r"/"
    t_INTDIVIDE = r"//"
    t_MOD = r"%"
    t_POWER = r"\^"
    t_CONVERSION = r"\(?->"
    t_RANGE = r"\.\."

    # Comparison operators
    t_EQ = r"=="
    t_NE = r"!="
    t_LE = r"<="
    t_GE = r">="
    t_LT = r"<"
    t_GT = r">"

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
    t_AT = r"@"
    t_BANG = r"!"

    def t_WHITESPACE(self, t):
        r"[\n\s]+"
        t.lexer.lineno += t.value.count("\n")
        return t

    # Identifiers and reserved words
    reserved_map = {}
    for r in reserved:
        reserved_map[r.lower()] = r

    def t_ID(self, t):
        r"(?:[^\W\d]|°)[\w°]*"
        t.type = self.reserved_map.get(t.value, "ID")
        return t

    # Number literal
    t_NUMBER = r"\d+(_\d+)* (\.\d+(_\d+)*)? ([eE][+-]? \d+(_\d+)* (\.\d+(_\d+)*)?)?"
    # String literal
    t_STRING = r"\"([^\\\n]|(\\.))*?\""

    def t_comment(self, t):
        r"(\#\[ (.|\n)* \]\#) | (\#.*)"
        t.lexer.lineno += t.value.count("\n")

    def t_error(self, t):
        t.value = t.value[0]
        e = SyntaxError()
        e.tok = t  # type: ignore
        raise e


def lex(source: str, module: ModuleMeta, debug=False) -> list[Token]:
    lexer = plylex.lex(module=LexTokens())
    errors = Exceptions(module=module)

    output: list[Token] = []
    lexer.lineno = 1
    lexer.lexpos = 0
    lexer.input(source)

    last_newline_pos = [0, 0]
    errored = False
    while True:
        try:
            tok = lexer.token()
        except SyntaxError as e:
            tok = e.tok  # type: ignore
            errored = True

        if not tok:
            break

        if tok.value.count("\n"):
            npos = len(tok.value) - tok.value[::-1].find("\n")
            last_newline_pos.append(tok.lexpos + npos)
            last_newline_pos.pop(0)

        token = Token(
            type=tok.type,
            value=tok.value,
            loc=Location(
                line=tok.lineno,
                col=tok.lexpos - last_newline_pos[-1] + 1,
                end_line=tok.lineno,
                end_col=tok.lexpos - last_newline_pos[-1] + len(tok.value),
            ),
        )
        if debug:
            print(token)

        if errored:
            errors.unexpectedToken(token)

        output.append(token)

    if debug:
        print("=" * 80)

    return output
