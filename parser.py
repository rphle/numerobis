from astnodes import AstNode, BinOp, Float, Integer
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
        return self.current_token

    def _ahead(self) -> Token:
        return self.tokens[0]

    def start(self) -> AstNode:
        return self.arith()

    def arith(self):
        node = self.term()
        while self.tokens and self._ahead().type in {"PLUS", "MINUS"}:
            op_token = self._consume()
            right = self.term()
            node = BinOp(op=op_token, left=node, right=right, loc=nodeloc(node, right))
        return node

    def term(self):
        node = self.factor()
        while self.tokens and self._ahead().type in {"TIMES", "DIVIDE", "MOD", "POWER"}:
            op_token = self._consume()
            right = self.factor()
            node = BinOp(op=op_token, left=node, right=right, loc=nodeloc(node, right))
        return node

    def factor(self) -> AstNode:
        tok = self._consume()
        if tok.type == "INTEGER":
            return Integer(value=tok.value, loc=tok.loc)
        elif tok.type == "FLOAT":
            return Float(value=tok.value, loc=tok.loc)
        elif tok.type == "LPAREN":
            node = self.arith()
            assert self._consume().type == "RPAREN"
            return node
        else:
            raise Exception(f"Unexpected token: {tok.type}")
