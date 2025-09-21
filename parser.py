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
    Conversion,
    Float,
    Function,
    Identifier,
    If,
    Integer,
    Operator,
    Param,
    UnaryOp,
    UnitDeclaration,
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
        while self.tok.type == "WHITESPACE":
            self.tok = self.tokens.pop(0)
        if types and (self.tok.type not in types):
            raise SyntaxError(f"Unexpected token {self.tok}")
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

    def start(self) -> list[AstNode]:
        statements = []
        while self._peek().type != "EOF":
            stmt = self.statement()
            statements.append(stmt)

            if self._peek().type == "SEMICOLON":
                self._consume("SEMICOLON")
        return statements

    def statement(self) -> AstNode:
        self._clear()
        first = self._peek()

        if first.type == "ID" and self._peek(2).type in {"ASSIGN", "COLON"}:
            """Variable declaration"""
            return self.assignment()
        elif first.type == "UNIT":
            """Unit declaration"""
            return self.unit_decl()
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

        return self.conversion()

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

    def unit_decl(self) -> AstNode:
        start = self._consume("UNIT")
        name = self._consume("ID")
        self._consume("ASSIGN")
        unit = self.unit()

        return UnitDeclaration(
            name=self._make_id(name),
            unit=unit,
            loc=nodeloc(start, unit[-1]),
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

    def conversion(self) -> AstNode:
        node = self.logic_or()
        if len(self.tokens) >= 2 and self._peek().type == "CONVERSION":
            op = self._make_op(self._consume())
            unit = self.unit()
            node = Conversion(op=op, value=node, unit=unit, loc=nodeloc(node, unit[-1]))
        return node

    def _logic_chain(self, subrule, op_type: str) -> AstNode:
        node = subrule()
        while self.tokens and self._peek().type == op_type:
            op = self._make_op(self._consume())
            right = subrule()
            node = BoolOp(op=op, left=node, right=right, loc=nodeloc(node, right))
        return node

    def logic_or(self) -> AstNode:
        return self._logic_chain(self.logic_xor, "OR")

    def logic_xor(self) -> AstNode:
        return self._logic_chain(self.logic_and, "XOR")

    def logic_and(self) -> AstNode:
        return self._logic_chain(self.logic_not, "AND")

    def logic_not(self) -> AstNode:
        if self._peek().type == "NOT":
            op = self._make_op(self._consume())
            operand = self.logic_not()
            return UnaryOp(op=op, operand=operand, loc=nodeloc(op, operand))
        return self.comparison()

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

    def _bin_chain(self, subrule, ops: set[str]) -> AstNode:
        node = subrule()
        while self.tokens and self._peek().type in ops:
            op = self._make_op(self._consume())
            right = subrule()
            node = BinOp(op=op, left=node, right=right, loc=nodeloc(node, right))
        return node

    def arith(self) -> AstNode:
        return self._bin_chain(self.term, {"PLUS", "MINUS"})

    def term(self) -> AstNode:
        return self._bin_chain(self.power, {"TIMES", "DIVIDE", "INTDIVIDE", "MOD"})

    def power(self) -> AstNode:
        node = self.unary()
        if self.tokens and self._peek().type == "POWER":
            op = self._make_op(self._consume())
            right = self.power()  # right-associative
            node = BinOp(op=op, left=node, right=right, loc=nodeloc(node, right))
        return node

    def unary(self) -> AstNode:
        if self._peek().type in {"PLUS", "MINUS"}:
            ops = []
            while self._peek().type in {"PLUS", "MINUS"}:
                op_token = self._consume()
                ops.append(op_token)

            operand = self.call()

            if sum(1 for op in ops if op.type == "MINUS") % 2 == 1:
                op = self._make_op(next(op for op in ops if op.type == "MINUS"))
                return UnaryOp(op=op, operand=operand, loc=nodeloc(op, operand))
            else:
                return operand

        return self.call()

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
            num = self._parse_number(tok)
            num.unit = self.unit()
            return num
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

    def unit(self):
        """
        Parse units after a number. A unit either follows a number directly or is separated from it by a whitespace.
        Units are chains of identifiers and numbers, separated by operators.
        An identifier following a number is considered a multiplication.
        The allowed operators are multiplication (*), division (/) and exponentiation (^).
        A unit may start with an ampersand (&).
        If the entire unit is enclosed in parentheses, it ends as soon as the closing parenthesis is encountered.
        """
        u = []
        parenthesized = False
        balance = 0
        start = self._peek(ignore_whitespace=False)

        if start.type == "WHITESPACE" and start.value == " ":
            self._clear()
            start = self._peek()

        if start.type == "AMPERSAND":
            self._consume("AMPERSAND")
            start = self._peek()

        if start.type in {"LPAREN", "ID"}:
            if start.type == "LPAREN":
                parenthesized = True

            while (tok := self._peek(ignore_whitespace=False)).type != "WHITESPACE":
                match tok.type:
                    case "ID":
                        if tok.value.startswith("_"):
                            raise Exception(f"Unexpected token: {tok.type}")
                        if len(u) > 0 and isinstance(u[-1], (Integer, Float)):
                            u.append(Operator(name="times"))
                        u.append(self._make_id(self._consume()))
                    case "NUMBER":
                        u.append(self._parse_number(self._consume()))
                    case "DIVIDE" | "TIMES" | "POWER":
                        if len(u) == 0 or isinstance(u[-1], Operator):
                            raise Exception(f"Unexpected token: {tok.type}")
                        u.append(self._make_op(self._consume()))
                    case "LPAREN" | "RPAREN":
                        if tok.type == "RPAREN" and (
                            balance == 0 or (len(u) > 0 and isinstance(u[-1], Operator))
                        ):
                            raise Exception(f"Unexpected token: {tok.type}")

                        balance += 1 if tok.type == "LPAREN" else -1
                        u.append(self._consume("LPAREN", "RPAREN"))
                        if balance == 0 and parenthesized:
                            break
                    case "EOF":
                        if balance == 0:
                            break
                        raise Exception(f"Unexpected token: {tok.type}")
                    case _:
                        raise Exception(f"Unexpected token: {tok.type}")

            if parenthesized:
                u = u[1:-1]

        return u

    def _make_id(self, tok: Token) -> Identifier:
        return Identifier(name=tok.value, loc=tok.loc)

    def _make_op(self, tok: Token) -> Operator:
        return Operator(name=tok.type.lower(), loc=tok.loc)

    def _parse_number(self, token: Token) -> Float | Integer:
        split = token.value.lower().split("e")
        number = split[0]
        exponent = split[1] if len(split) > 1 else ""
        if "." in exponent:
            raise Exception(f"Invalid number literal: {token.value}")
        if "." in number or exponent.startswith("-"):
            return Float(value=number, exponent=exponent, unit=[], loc=token.loc)
        else:
            return Integer(value=number, exponent=exponent, unit=[], loc=token.loc)

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
