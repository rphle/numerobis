from dataclasses import dataclass
from typing import Optional

from classes import ModuleMeta
from nodes.ast import Identifier
from nodes.core import Token
from nodes.unit import Constant, Expression, Neg, Power, Product, Scalar, Sum, UnitNode

from ..template import ParserTemplate


@dataclass()
class UnitParserConfig:
    standalone: bool = False
    calls: bool = False
    unitful_numbers: bool = False
    constants: bool = False
    addition: bool = False
    scalars: bool = False


class UnitParser(ParserTemplate):
    def __init__(
        self, tokens: list[Token], module: ModuleMeta, config: UnitParserConfig
    ):
        super().__init__(tokens=tokens, module=module)
        self.config = config

    def peek(self, n: int = 1, ignore_whitespace: bool | None = None):
        return self._peek(
            n=n,
            ignore_whitespace=self.config.standalone
            if not ignore_whitespace
            else ignore_whitespace,
        )

    def start(self) -> Optional[Expression]:
        self._clear()

        if self._peek().type not in {"ID", "NUMBER", "LPAREN"}:
            return None

        parenthesized = False
        if self._peek().type == "LPAREN" and not self.config.calls:
            self._consume("LPAREN")
            self.config.standalone = True
            parenthesized = True

        unit = self.sum()

        if self.config.standalone and parenthesized:
            self._consume("RPAREN")

        return Expression(value=unit)

    def sum(self) -> UnitNode:
        result = Sum([])
        result.add(self.product())

        if not self.config.addition and self.peek().type in ["PLUS", "MINUS"]:
            self.errors.throw(
                16,
                operator={"PLUS": "+", "MINUS": "-"}[self.peek().type],
                loc=self.peek().loc,
            )

        while self.tokens and self.peek().type in ["PLUS", "MINUS"]:
            self._consume("PLUS", "MINUS")

            if self.tok.type == "PLUS":
                result.add(self.product())
            elif self.tok.type == "MINUS":
                value = self.product()
                result.add(Neg(value=value, loc=value.loc))

        if len(result.values) == 1:
            return result.values[0]
        return result

    def product(self) -> UnitNode:
        result = Product([])
        result.add(self.power())

        while self.tokens and self.peek().type in ["TIMES", "DIVIDE"]:
            self._consume("TIMES", "DIVIDE")
            if self.tok.type == "TIMES":
                result.add(self.power())
            elif self.tok.type == "DIVIDE":
                value = self.power()
                result.add(Power(base=value, exponent=Scalar(-1), loc=value.loc))

        if len(result.values) == 1:
            return result.values[0]
        return result

    def power(self) -> UnitNode:
        value = self.unary()
        if self.tokens and self.peek().type == "POWER":
            self._consume("POWER")
            if self.peek().type == "NUMBER":
                exponent = self._parse_number(self._consume("NUMBER"))
            else:
                self._consume("LPAREN")
                exponent = self.sum()
                self._consume("RPAREN")

            value = Power(
                base=value, exponent=exponent, loc=value.loc.merge(exponent.loc)
            )
        return value

    def unary(self) -> UnitNode:
        if self.peek().type in {"PLUS", "MINUS"}:
            ops = []
            while self.peek().type in {"PLUS", "MINUS"}:
                op_token = self._consume()
                ops.append(op_token)

            operand = self.atom()

            if sum(1 for op in ops if op.type == "MINUS") % 2 == 1:
                return Neg(value=operand, loc=operand.loc)
            return operand

        return self.atom()

    def atom(self) -> UnitNode:
        tok = self._consume("ID", "NUMBER", "LPAREN")
        match tok.type:
            case "NUMBER":
                num = self._parse_number(tok)
                return num
            case "ID":
                if tok.value == "_":
                    return self._parse_placeholder(tok)
                return Identifier(name=tok.value, loc=tok.loc)
            case "LPAREN":
                node = self.sum()
                self._consume("RPAREN")
                return node
            case "AT":
                """Reference constant/parameter"""
                if not self.config.constants:
                    self.errors.unexpectedToken(
                        tok, help="constants cannot be referenced here"
                    )
                if self._peek(ignore_whitespace=False).type != "ID":
                    self.errors.throw(9, loc=tok.loc)
                node = self._consume("ID")
                node.value = "@" + node.value
                return Constant(name=tok.value, loc=tok.loc)
            case _:
                raise SyntaxError(f"Unexpected token {tok}")

    def _parse_number(self, token: Token) -> Scalar:
        split = token.value.lower().split("e")
        number = split[0].replace("_", "")
        exponent = split[1] if len(split) > 1 else ""
        if "." in exponent:
            self.errors.throw(7, token=token.value, loc=token.loc)

        if self.config.unitful_numbers:
            _unitparser = UnitParser(
                tokens=self.tokens, module=self.module, config=UnitParserConfig()
            )
            unit = _unitparser.start()
            self.tokens = _unitparser.tokens
        else:
            unit = None

        exponent = float(exponent) if exponent else 0

        return Scalar(value=float(number) * 10**exponent, unit=unit, loc=token.loc)

    def _parse_placeholder(self, token: Token):
        assert token.value == "_"

        if self.config.unitful_numbers:
            _unitparser = UnitParser(
                tokens=self.tokens, module=self.module, config=UnitParserConfig()
            )
            unit = _unitparser.start()
            self.tokens = _unitparser.tokens
            if unit is not None:
                return Scalar(value=1, unit=unit, loc=token.loc.merge(unit.loc))
        return Identifier(name=token.value, loc=token.loc)
