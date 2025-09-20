from itertools import islice

from astnodes import (
    Assign,
    AstNode,
    BinOp,
    Block,
    Boolean,
    BoolOp,
    Call,
    CallArg,
    Compare,
    Float,
    Function,
    Identifier,
    If,
    Integer,
    Operator,
    Param,
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

    def _consume(self, *types: str) -> Token:
        if self._peek().type == "EOF":
            raise Exception("Unexpected EOF")

        self.tok = self.tokens.pop(0)
        while self.tok.type in {"WHITESPACE", "SEMICOLON"}:
            self.tok = self.tokens.pop(0)
        if types and (self.tok.type not in types):
            raise SyntaxError(f"Unexpected token {self.tok}")
        return self.tok

    def _clear(self):
        while self._peek(ignore_whitespace=False).type in {"WHITESPACE", "SEMICOLON"}:
            self.tokens.pop(0)

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
        while self._peek().type != "EOF":
            stmt = self.statement()
            statements.append(stmt)
        return statements

    def statement(self) -> AstNode:
        self._clear()
        first = self._peek()

        if first.type == "ID" and self._peek(2).type in {"ASSIGN", "COLON"}:
            """Variable declaration"""
            return self.assignment()
        elif (
            first.type == "ID"
            and self._peek(2).type == "LPAREN"
            and self._check_function(start=3)
        ):
            """Function declaration"""
            return self.function()
        return self.expression()

    def expression(self) -> AstNode:
        first = self._peek()
        if first.type == "LBRACE":
            """Block"""
            return self.block()
        elif first.type == "IF":
            """Conditional"""
            return self.conditional()

        return self.logic_or()

    def block(self) -> AstNode:
        start = self._consume()
        body = []
        while self.tokens and self._peek().type != "RBRACE":
            body.append(self.statement())
        end = self._consume()
        return Block(body=body, loc=nodeloc(start, end))

    def assignment(self) -> AstNode:
        name = self._consume()
        type_token = None
        if self._peek().type == "COLON":
            self._consume()
            type_token = self._consume()
        _equals_token = self._consume()
        expr = self.expression()

        return Assign(
            target=Identifier(name=name.value, loc=name.loc),
            value=expr,
            type=Identifier(name=type_token.value, loc=type_token.loc)
            if type_token
            else None,
            loc=nodeloc(name, expr),
        )

    def function(self) -> AstNode:
        name = self._make_id(self._consume("ID"))
        return_type = None

        self._consume("LPAREN")

        params = []
        while self._peek().type != "RPAREN":
            p = {"name": self._make_id(self._consume("ID"))}

            if self._peek().type == "COLON":
                self._consume("COLON")
                p["type"] = self._make_id(self._consume("ID"))

            if self._peek().type == "ASSIGN":
                self._consume("ASSIGN")
                p["default"] = self.expression()  # type: ignore

            params.append(
                Param(
                    name=p["name"],
                    type=p.get("type"),
                    default=p.get("default"),  # type: ignore
                    loc=nodeloc(p["name"], p.get("default", p.get("type", p["name"]))),
                )
            )

            if self._peek().type == "RPAREN":
                break
            self._consume("COMMA")

        self._consume("RPAREN")
        self._consume("COLON", "ASSIGN")
        if self.tok.type == "COLON":
            return_type = self._make_id(self._consume("ID"))
            self._consume("ASSIGN")

        body = self.expression()

        node = Function(
            name=name,
            params=params,
            return_type=return_type,
            body=body,
            loc=nodeloc(name, body),
        )
        return node

    def conditional(self) -> AstNode:
        self._consume()
        condition = self.expression()
        self._consume()
        then_branch = self.expression()
        else_branch = None
        if self._peek().type == "ELSE":
            self._consume()
            else_branch = self.expression()

        return If(
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
            loc=nodeloc(condition, else_branch if else_branch else then_branch),
        )

    def logic_or(self) -> AstNode:
        node = self.logic_and()
        while self.tokens and self._peek().type == "OR":
            op = self._make_op(self._consume())
            right = self.logic_and()
            node = BoolOp(op=op, left=node, right=right, loc=nodeloc(node, right))
        return node

    def logic_and(self) -> AstNode:
        node = self.comparison()
        while self.tokens and self._peek().type == "AND":
            op = self._make_op(self._consume())
            right = self.comparison()
            node = BoolOp(op=op, left=node, right=right, loc=nodeloc(node, right))
        return node

    def comparison(self) -> AstNode:
        node = self.arith()
        ops = []
        comparators = []
        while self.tokens and self._peek().type in {"LT", "LE", "GT", "GE", "EQ", "NE"}:
            op = self._make_op(self._consume())
            right = self.arith()
            ops.append(op)
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
            op = self._make_op(self._consume())
            right = self.term()
            node = BinOp(op=op, left=node, right=right, loc=nodeloc(node, right))
        return node

    def term(self) -> AstNode:
        node = self.call()
        while self.tokens and self._peek().type in {"TIMES", "DIVIDE", "MOD", "POWER"}:
            op = self._make_op(self._consume())
            right = self.call()
            node = BinOp(op=op, left=node, right=right, loc=nodeloc(node, right))
        return node

    def call(self) -> AstNode:
        node = self.atom()
        while self._peek().type == "LPAREN":
            self._consume("LPAREN")
            args = []
            while self._peek().type != "RPAREN":
                name = None
                if self._peek(2).type == "ASSIGN":
                    name = self._make_id(self._consume("ID"))
                    self._consume("ASSIGN")
                arg = self.expression()

                args.append(
                    CallArg(
                        name=name, value=arg, loc=nodeloc(name if name else arg, arg)
                    )
                )

                if self._peek().type == "RPAREN":
                    break
                self._consume("COMMA")

            end = self._consume("RPAREN")
            node = Call(callee=node, args=args, loc=nodeloc(node, end))
        return node

    def atom(self) -> AstNode:
        tok = self._consume()
        if tok.type == "NUMBER":
            return self._parse_number(tok)
        elif tok.type in {"TRUE", "FALSE"}:
            return Boolean(value=tok.value == "TRUE", loc=tok.loc)
        elif tok.type == "ID":
            return self._make_id(tok)
        elif tok.type == "LPAREN":
            node = self.expression()
            assert self._consume().type == "RPAREN"
            return node
        else:
            raise Exception(f"Unexpected token: {tok.type}")

    def _make_id(self, tok: Token) -> Identifier:
        return Identifier(name=tok.value, loc=tok.loc)

    def _make_op(self, tok: Token) -> Operator:
        return Operator(name=tok.type.lower(), loc=tok.loc)

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

    def _check_function(self, start: int = 3):
        i = start
        balance = 1

        while True:
            tok = self._peek(i).type
            if balance == 0:
                return tok in {"COLON", "ASSIGN"}
            elif tok in ["LPAREN", "RPAREN"]:
                balance += 1 if tok == "LPAREN" else -1
            elif tok == "EOF":
                raise Exception("Unexpected EOF")
            i += 1
