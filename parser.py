from itertools import islice

from astnodes import (
    Assign,
    AstNode,
    BinOp,
    BoolOp,
    Compare,
    Float,
    Identifier,
    Integer,
)
from classes import Location
from lexer import Token


def nodeloc(*nodes: Token | AstNode):
    return Location(
        line=nodes[0].loc.line,
        col=nodes[0].loc.col,
        start=nodes[0].loc.start,
        end=nodes[-1].loc.end,
    )


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.tok = None

    def _consume(self) -> Token:
        self.tok = self.tokens.pop(0)
        while self.tok.type in {"WHITESPACE", "SEMICOLON"}:
            self.tok = self.tokens.pop(0)
        return self.tok

    def _peek(self, n: int = 1, ignore_whitespace=True) -> Token:
        EOF = Token(type="EOF", value="EOF", loc=Location())
        if ignore_whitespace:
            return next(
                islice(
                    (
                        tok
                        for tok in self.tokens
                        if tok.type not in {"WHITESPACE", "SEMICOLON"}
                    ),
                    n - 1,
                    n,
                ),
                EOF,
            )
        else:
            return self.tokens[n - 1] if self.tokens else EOF

    def start(self) -> list[AstNode]:
        statements = []
        while self.tokens:
            stmt = self.statement()
            statements.append(stmt)

        return statements

    def statement(self) -> AstNode:
        first = self._peek()
        if first and first.type == "ID" and len(self.tokens) > 1:
            second = self._peek(2)
            if second.type in {"EQUALS", "COLON"}:
                return self.assignment()

        return self.logic_or()

    def assignment(self) -> AstNode:
        id_token = self._consume()
        type_token = None
        if self._peek().type == "COLON":
            self._consume()
            type_token = self._consume()
        equals_token = self._consume()
        expr = self.logic_or()

        return Assign(
            target=Identifier(name=id_token.value, loc=id_token.loc),
            value=expr,
            type=Identifier(name=type_token.value, loc=type_token.loc)
            if type_token
            else None,
            loc=nodeloc(id_token, expr),
        )

    def logic_or(self) -> AstNode:
        node = self.logic_and()
        while self.tokens and self._peek().type == "OR":
            op_token = self._consume()
            right = self.logic_and()
            node = BoolOp(op=op_token, left=node, right=right, loc=nodeloc(node, right))
        return node

    def logic_and(self) -> AstNode:
        node = self.comparison()
        while self.tokens and self._peek().type == "AND":
            op_token = self._consume()
            right = self.comparison()
            node = BoolOp(op=op_token, left=node, right=right, loc=nodeloc(node, right))
        return node

    def comparison(self) -> AstNode:
        node = self.arith()
        ops = []
        comparators = []
        while self.tokens and self._peek().type in {"LT", "LE", "GT", "GE", "EQ", "NE"}:
            op_token = self._consume()
            right = self.arith()
            ops.append(op_token)
            comparators.append(right)
        if ops:
            return Compare(
                left=node,
                ops=ops,
                comparators=comparators,
                loc=nodeloc(node, comparators[-1]),
            )
        else:
            return node

    def arith(self) -> AstNode:
        node = self.term()
        while self.tokens and self._peek().type in {"PLUS", "MINUS"}:
            op_token = self._consume()
            right = self.term()
            node = BinOp(op=op_token, left=node, right=right, loc=nodeloc(node, right))
        return node

    def term(self) -> AstNode:
        node = self.factor()
        while self.tokens and self._peek().type in {"TIMES", "DIVIDE", "MOD", "POWER"}:
            op_token = self._consume()
            right = self.factor()
            node = BinOp(op=op_token, left=node, right=right, loc=nodeloc(node, right))
        return node

    def factor(self) -> AstNode:
        tok = self._consume()
        if tok.type == "NUMBER":
            return self._parse_number(tok)
        elif tok.type == "ID":
            return Identifier(name=tok.value, loc=tok.loc)
        elif tok.type == "LPAREN":
            node = self.logic_or()
            assert self._consume().type == "RPAREN"
            return node
        else:
            raise Exception(f"Unexpected token: {tok.type}")

    def _parse_number(self, token: Token) -> AstNode:
        split = token.value.lower().split("e")
        number = split[0]
        exponent = split[1] if len(split) > 1 else ""
        if "." in exponent:
            raise Exception(f"Invalid number literal: {token.value}")
        if "." in number:
            return Float(value=number, exponent=exponent, loc=token.loc)
        else:
            return Integer(value=number, exponent=exponent, loc=token.loc)
