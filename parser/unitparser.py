import dataclasses
from parser.template import ParserTemplate

from astnodes import (
    AstNode,
    BinOp,
    Call,
    CallArg,
    Location,
    Scalar,
    Token,
    UnaryOp,
    Unit,
    nodeloc,
)
from classes import ModuleMeta
from exceptions import uSyntaxError


class UnitParser(ParserTemplate):
    def __init__(
        self,
        tokens: list[Token],
        module: ModuleMeta,
        standalone: bool = False,
    ):
        super().__init__(tokens=tokens, module=module)
        self.standalone = standalone

    def peek(self, n: int = 1, ignore_whitespace: bool | None = None):
        return self._peek(
            n=n,
            ignore_whitespace=self.standalone
            if not ignore_whitespace
            else ignore_whitespace,
        )

    def start(self) -> Unit:
        self._clear()
        parenthesized = False
        if self._peek().type == "LPAREN" and not self.standalone:
            self._consume("LPAREN")
            self.standalone = True
            parenthesized = True

        unit = self.expression()

        if self.standalone and parenthesized:
            self._consume("RPAREN")
        return self._make_unit(unit)

    def expression(self) -> list[AstNode]:
        nodes = [self.power()]

        while self.tokens and self.peek().type in {"TIMES", "DIVIDE"}:
            nodes.append(self._make_op(self._consume()))
            nodes.append(self.power())

        if self.peek().type in {"PLUS", "MINUS", "MOD", "INTDIVIDE"}:
            self.errors.unexpectedToken(
                self.peek(),
                help=f"{self.peek().value} is not a valid operator in unit expressions",
            )

        return nodes

    def power(self) -> AstNode:
        node = self.unary()
        if self.tokens and self.peek().type == "POWER":
            op = self._make_op(self._consume())
            if self.peek().type != "NUMBER":
                self.errors.unexpectedToken(
                    self.peek(),
                    help="Exponent must be a dimensionless scalar",
                )
            right = self._parse_number(self._consume("NUMBER"))
            node = BinOp(op=op, left=node, right=right, loc=nodeloc(node, right))
        return node

    def unary(self) -> AstNode:
        if self.peek().type in {"PLUS", "MINUS"}:
            ops = []
            while self.peek().type in {"PLUS", "MINUS"}:
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
        if self.peek(ignore_whitespace=False).type == "LPAREN":
            self.errors.unexpectedToken(
                self.peek(),
                help="Did you mean to call a parameterized unit? Use brackets […] instead of parentheses.",
            )

        while self.peek(ignore_whitespace=False).type == "LBRACKET":
            self._consume("LBRACKET")
            args = []
            while self.peek().type != "RBRACKET":
                name = None
                if self.peek(2).type == "ASSIGN":
                    name = self._make_id(self._consume("ID"))
                    self._consume("ASSIGN")
                arg = self.expression()

                args.append(
                    CallArg(
                        name=name,
                        value=self._make_unit(arg),
                        loc=nodeloc(name if name else arg[0], arg[-1]),
                    )
                )

                if self.peek().type == "RBRACKET":
                    break
                self._consume("COMMA")

            end = self._consume("RBRACKET")
            node = Call(callee=node, args=args, loc=nodeloc(node, end))
        return node

    def atom(self) -> AstNode:
        tok = self._consume("NUMBER", "ID", "AT", "LPAREN")
        match tok.type:
            case "NUMBER":
                num = self._parse_number(tok)
                num = Scalar(value=num.value, exponent=num.exponent, loc=num.loc)
                return num
            case "ID":
                return self._make_id(tok)
            case "LPAREN":
                node = self.expression()
                self._consume("RPAREN")
                unit = self._make_unit(node)
                unit = dataclasses.replace(unit, loc=nodeloc(unit, self.tok))
                return unit
            case "AT":
                """Reference parameter"""
                if self._peek(ignore_whitespace=False).type != "ID":
                    uSyntaxError(
                        message="Expected identifier",
                        module=self.module,
                        loc=Location(line=self.tok.loc.line, col=self.tok.loc.col + 1),
                    )
                if not self.standalone:
                    uSyntaxError(
                        message="Parameters can only be referenced in unit declarations",
                        module=self.module,
                        loc=Location(line=self.tok.loc.line, col=self.tok.loc.col + 1),
                    )
                node = self._consume("ID")
                node.value = "@" + node.value
                return self._make_id(node)
            case _:
                raise SyntaxError(f"Unexpected token {tok}")

    def _make_unit(self, unit: list[AstNode]) -> Unit:
        return Unit(unit=unit, loc=nodeloc(unit[0], unit[-1]))
