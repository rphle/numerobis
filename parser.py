from itertools import islice
from typing import Literal, Optional

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
        self.tok = None

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
            and self._peek(2, ignore_whitespace=False).type == "LPAREN"
        ):
            """Function definition or call"""
            return self.func_or_call()
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

    def func_or_call(
        self, type_: Optional[Literal["function", "call"]] = None
    ) -> AstNode:
        name = self._consume("ID")
        self._consume("LPAREN")

        return_type = None
        params = []

        while True:
            # parse parameters/arguments
            p = {}
            first = self._consume()
            second = self._peek()

            if first.type == "RPAREN":
                break

            if second.type == "COLON":
                # Type-annotated function parameter
                if first.type == "ID":
                    p["name"] = first
                else:
                    raise SyntaxError(f"Unexpected token {first}")
                p["_colon"] = self._consume()

                if (third := self._consume()).type == "ID":
                    p["type"] = third
                else:
                    raise SyntaxError(f"Unexpected token {third}")

                if self._peek().type == "ASSIGN":
                    p["_assign"] = self._consume()
                    p["value"] = self.expression()

            elif second.type == "ASSIGN":
                # Function parameter with default value or keyword argument
                if first.type == "ID":
                    p["name"] = first
                else:
                    raise SyntaxError(f"Unexpected token {first}")
                p["_assign"] = self._consume()
                p["value"] = self.expression()

            elif second.type in {"COMMA", "RPAREN"}:
                # Basic function parameter
                if first.type == "ID":
                    p["name"] = first
                else:
                    p["value"] = first
            else:
                raise SyntaxError(f"Unexpected token {first}")

            params.append(p)
            if self._consume("COMMA", "RPAREN").type == "RPAREN":
                break

        if (
            self._peek().type in {"ASSIGN", "COLON"}
            and all("name" in p for p in params)
            and type_ in {None, "function"}
        ):
            # Function definition
            if self._consume().type == "COLON":
                # Parse return type
                if self._peek().type == "ID":
                    self._consume()
                    return_type = self._consume()
                    return_type = Identifier(
                        name=return_type.value, loc=return_type.loc
                    )
                else:
                    raise SyntaxError(f"Unexpected token {self._peek()}")

            body = self.expression()

            params = [
                Param(
                    name=Identifier(name=p["name"].value, loc=p["name"].loc),
                    type=p.get("type"),
                    default=p.get("value"),
                    loc=nodeloc(p["name"], p.get("value", p.get("type", p["name"]))),
                )
                for p in params
            ]

            return Function(
                name=Identifier(name=name.value, loc=name.loc),
                params=params,
                return_type=return_type,
                body=body,
                loc=nodeloc(name, body),
            )
        elif colon := next((p["_colon"] for p in params if "_colon" in p), None):
            # Function definition with type annotations but without body
            # -or-
            # Call with type annotations (syntax error), we parse it as a function call
            raise SyntaxError(f"Unexpected token {colon}")
        elif type_ in {None, "call"}:
            # Function call
            args = [
                CallArg(
                    name=Identifier(name=p["name"].value, loc=p["name"].loc)
                    if "name" in p
                    else None,
                    value=p.get("value"),
                    loc=nodeloc(p.get("name", p["value"]), p["value"]),
                )
                for p in params
            ]
            return Call(
                callee=Identifier(name=name.value, loc=name.loc),
                args=args,
                loc=nodeloc(name, name),
            )
        else:
            raise SyntaxError("Function/call distinction error")

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
        elif tok.type in {"TRUE", "FALSE"}:
            return Boolean(value=tok.value == "TRUE", loc=tok.loc)
        elif tok.type == "ID":
            return Identifier(name=tok.value, loc=tok.loc)
        elif tok.type == "LPAREN":
            node = self.logic_or()
            assert self._consume().type == "RPAREN"
            return node
        elif tok.type == "COMMA":
            node = self.logic_or()
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
