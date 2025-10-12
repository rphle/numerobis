from itertools import islice

from astnodes import Float, Identifier, Integer, Location, Operator, Token, Unit
from classes import ModuleMeta
from exceptions import Exceptions, uSyntaxError


class ParserTemplate:
    def __init__(self, tokens: list[Token], module: ModuleMeta):
        self.tokens = tokens
        self.module = module
        self.errors = Exceptions(module=module)

    def _consume(self, *types: str, ignore_whitespace=True) -> Token:
        if self._peek().type == "EOF":
            self.errors.unexpectedEOF(loc=self._peek().loc)

        self.tok = self.tokens.pop(0)
        while ignore_whitespace and self.tok.type == "WHITESPACE":
            self.tok = self.tokens.pop(0)
        if types and (self.tok.type not in types):
            self.errors.unexpectedToken(self.tok)
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
            return self.tokens[n - 1] if len(self.tokens) >= n else EOF

    def _make_id(self, tok: Token) -> Identifier:
        return Identifier(name=tok.value, loc=tok.loc)

    def _make_op(self, tok: Token) -> Operator:
        names = {
            "plus": "add",
            "minus": "sub",
            "times": "mul",
            "divide": "div",
            "intdivide": "intdiv",
            "power": "pow",
            "modulo": "mod",
        }
        name = tok.type.lower()
        return Operator(name=names.get(name, name), loc=tok.loc)

    def _parse_number(self, token: Token) -> Float | Integer:
        split = token.value.lower().split("e")
        number = split[0].replace("_", "")
        exponent = split[1] if len(split) > 1 else ""
        if "." in exponent:
            self.errors.throw(
                uSyntaxError, f"Invalid number literal: {token.value}", loc=token.loc
            )

        unit = Unit(unit=[])
        if "." in number or exponent.startswith("-"):
            return Float(value=number, exponent=exponent, unit=unit, loc=token.loc)
        else:
            return Integer(value=number, exponent=exponent, unit=unit, loc=token.loc)
