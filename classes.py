from itertools import islice

from astnodes import AstNode, Float, Identifier, Integer, Location, Operator, Token
from exceptions import uSyntaxError


def nodeloc(*nodes: Token | AstNode):
    return Location(
        line=nodes[0].loc.line,
        col=nodes[0].loc.col,
        start=nodes[0].loc.start,
        span=(nodes[-1].loc.start - nodes[0].loc.start) + nodes[-1].loc.span,
    )


class Errors:
    def __init__(self, path: str | None):
        self.path = path

    def unexpected(
        self, tok: Token, value: str | None = None, loc: Location | None = None
    ):
        uSyntaxError(
            f"Unexpected token: '{value or tok.value}'",
            path=self.path,
            loc=loc or tok.loc,
        )


class ParserTemplate:
    def __init__(self, tokens: list[Token], path: str | None = None):
        self.tokens = tokens
        self.path = path
        self.errors = Errors(path)

    def _consume(self, *types: str, ignore_whitespace=True) -> Token:
        if self._peek().type == "EOF":
            uSyntaxError("Unexpected EOF", path=self.path)

        self.tok = self.tokens.pop(0)
        while ignore_whitespace and self.tok.type == "WHITESPACE":
            self.tok = self.tokens.pop(0)
        if types and (self.tok.type not in types):
            self.errors.unexpected(self.tok)
        return self.tok

    def _clear(self):
        while self._peek(ignore_whitespace=False).type == "WHITESPACE":
            self.tokens.pop(0)

    def _peek(self, n: int = 1, ignore_whitespace=True) -> Token:
        EOF = Token(type="EOF", value="EOF", loc=Location())
        if ignore_whitespace:
            return next(
                islice(
                    (tok for tok in self.tokens if tok.type != "WHITESPACE"),
                    n - 1,
                    n,
                ),
                EOF,
            )
        else:
            return self.tokens[n - 1] if self.tokens else EOF

    def _make_id(self, tok: Token) -> Identifier:
        return Identifier(name=tok.value, loc=tok.loc)

    def _make_op(self, tok: Token) -> Operator:
        return Operator(name=tok.type.lower(), loc=tok.loc)

    def _parse_number(self, token: Token) -> Float | Integer:
        split = token.value.lower().split("e")
        number = split[0].replace("_", "")
        exponent = split[1] if len(split) > 1 else ""
        if "." in exponent:
            uSyntaxError(
                f"Invalid number literal: {token.value}", path=self.path, loc=token.loc
            )
        if "." in number or exponent.startswith("-"):
            return Float(value=number, exponent=exponent, unit=None, loc=token.loc)
        else:
            return Integer(value=number, exponent=exponent, unit=None, loc=token.loc)
