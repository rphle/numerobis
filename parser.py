from astnodes import AstNode, BinOp, BoolOp, Compare, Float, Integer
from classes import Location
from lexer import Token


def nodeloc(*nodes: Token | AstNode):
    return Location(
        line=nodes[0].loc.line,
        col=nodes[0].loc.col,
        start=nodes[-1].loc.start,
        end=nodes[-1].loc.end,
    )


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.current_token = None

    def _consume(self) -> Token:
        self.current_token = self.tokens.pop(0)
        while self.current_token.type == "WHITESPACE":
            self.current_token = self.tokens.pop(0)
        return self.current_token

    def _ahead(self, whitespace: bool = False) -> Token:
        if whitespace:
            return self.tokens[0]
        return next(tok for tok in self.tokens if tok.type != "WHITESPACE")

    def start(self) -> AstNode:
        return self.logic_or()

    def logic_or(self) -> AstNode:
        node = self.logic_and()
        while self.tokens and self._ahead().type == "OR":
            op_token = self._consume()
            right = self.logic_and()
            node = BoolOp(op=op_token, left=node, right=right, loc=nodeloc(node, right))
        return node

    def logic_and(self) -> AstNode:
        node = self.comparison()
        while self.tokens and self._ahead().type == "AND":
            op_token = self._consume()
            right = self.comparison()
            node = BoolOp(op=op_token, left=node, right=right, loc=nodeloc(node, right))
        return node

    def comparison(self) -> AstNode:
        node = self.arith()
        ops = []
        comparators = []
        # Accept chains like a < b <= c
        while self.tokens and self._ahead().type in {
            "LT",
            "LE",
            "GT",
            "GE",
            "EQ",
            "NE",
        }:
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
        while self.tokens and self._ahead().type in {"PLUS", "MINUS"}:
            op_token = self._consume()
            right = self.term()
            node = BinOp(op=op_token, left=node, right=right, loc=nodeloc(node, right))
        return node

    def term(self) -> AstNode:
        node = self.factor()
        while self.tokens and self._ahead().type in {"TIMES", "DIVIDE", "MOD", "POWER"}:
            op_token = self._consume()
            right = self.factor()
            node = BinOp(op=op_token, left=node, right=right, loc=nodeloc(node, right))
        return node

    def factor(self) -> AstNode:
        tok = self._consume()
        if tok.type == "NUMBER":
            return self._parse_number(tok)
        elif tok.type == "LPAREN":
            node = self.logic_or()
            assert self._consume().type == "RPAREN"
            return node
        else:
            raise Exception(f"Unexpected token: {tok.type}")

    def _parse_number(self, token: Token):
        split = token.value.lower().split("e")
        number = split[0]
        exponent = split[1] if len(split) > 1 else ""

        if "." in exponent:
            raise Exception(f"Invalid number literal: {token.value}")

        if "." in number:
            return Float(value=number, exponent=exponent, loc=token.loc)
        else:
            return Integer(value=number, exponent=exponent, loc=token.loc)
