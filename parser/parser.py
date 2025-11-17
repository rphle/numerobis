import dataclasses
import math
from parser.template import ParserTemplate
from parser.unitparser import UnitParser

from astnodes import (
    AstNode,
    BinOp,
    Block,
    Boolean,
    BoolOp,
    Break,
    Call,
    CallArg,
    Compare,
    Continue,
    Conversion,
    DimensionDefinition,
    ForLoop,
    FromImport,
    Function,
    Identifier,
    If,
    Import,
    Index,
    List,
    Location,
    Param,
    Range,
    Return,
    Slice,
    String,
    Token,
    Tuple,
    UnaryOp,
    Unit,
    UnitDefinition,
    Variable,
    WhileLoop,
    nodeloc,
)
from classes import ModuleMeta
from exceptions import uSyntaxError


class Parser(ParserTemplate):
    def __init__(self, tokens: list[Token], module: ModuleMeta):
        super().__init__(tokens=tokens, module=module)

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
            return self.variable()
        elif first.type == "DIMENSION":
            """Dimension declaration"""
            return self.dimension_def()
        elif first.type == "UNIT":
            """Unit declaration"""
            return self.unit_def()
        elif first.type == "IF":
            """Conditional statement"""
            return self.conditional()
        elif first.type == "FOR":
            """For loop"""
            return self.forloop()
        elif first.type == "WHILE":
            """While loop"""
            return self.whileloop()
        elif first.type == "BREAK":
            """Break statement"""
            self._consume("BREAK")
            return Break(loc=self.tok.loc)
        elif first.type == "CONTINUE":
            """Continue statement"""
            self._consume("CONTINUE")
            return Continue(loc=self.tok.loc)
        elif first.type == "IMPORT":
            """Import statement"""
            return self.import_stmt()
        elif first.type == "FROM":
            """From import statement"""
            return self.from_import_stmt()
        elif first.type == "ID" and self._peek(2).type == "BANG":
            """Function declaration"""
            return self.function()
        return self.block()

    def block(self) -> AstNode:
        """
        Blocks are a mix of statements and expressions, mostly to allow cleaner control structure syntax
        """
        if self._peek().type == "LBRACE":
            start = self._consume("LBRACE")
            body = []
            while self.tokens and self._peek().type != "RBRACE":
                body.append(self.statement())
                if self._peek().type == "SEMICOLON":
                    self._consume("SEMICOLON")

            end = self._consume("RBRACE")
            return Block(body=body, loc=nodeloc(start, end))
        elif self._peek().type == "RETURN":
            """Return statement"""
            ret = self._consume("RETURN")
            value = (
                self.expression()
                if not any(
                    x in self._peek(ignore_whitespace=False).value for x in ["\n", ";"]
                )
                else None
            )
            loc = ret.loc.merge(value.loc) if value else ret.loc
            return Return(value=value, loc=loc)

        return self.expression()

    def expression(self) -> AstNode:
        first = self._peek()
        if first.type == "IF":
            """Conditional expression"""
            return self.conditional(expression=True)
        elif first.type == "AT":
            """Reference unit namespace"""
            if self._peek(2, ignore_whitespace=False).type not in {"LPAREN", "ID"}:
                self.errors.throw(
                    uSyntaxError,
                    message="Expected unit",
                    loc=Location(line=self.tok.loc.line, col=self.tok.loc.col + 1),
                )
            self._consume("AT")
            return self.unit()
        elif self._peek().type == "BANG":
            return self.function(anonymous=True)

        return self.conversion()

    def variable(self) -> AstNode:
        name = self._consume("ID")
        type_token = None
        if self._peek().type == "COLON":
            self._consume("COLON")
            type_token = self.unit(standalone=True)

        self._consume("ASSIGN")
        expr = self.block()

        return Variable(
            name=Identifier(name=name.value, loc=name.loc),
            value=expr,
            type=type_token if type_token else None,
            loc=nodeloc(name, expr),
        )

    def dimension_def(self) -> AstNode:
        start = self._consume("DIMENSION")
        name = self._consume("ID")
        value = None
        if self._peek().type == "ASSIGN":
            self._consume("ASSIGN")
            self._clear()
            value = self.unit(standalone=True)

        return DimensionDefinition(
            name=self._make_id(name),
            value=value,
            loc=nodeloc(start, value or name),
        )

    def unit_def(self) -> AstNode:
        start = self._consume("UNIT")
        name = self._consume("ID")

        dimension = None
        if self._peek().type == "COLON":
            self._consume("COLON")
            dimension = self._make_id(self._consume("ID"))

        params = []
        if self._peek().type == "LPAREN":
            self.errors.unexpectedToken(
                self._peek(),
                help="Did you mean to define a parameterized unit? Use brackets […] instead of parentheses.",
            )
        if self._peek().type == "LBRACKET":
            """
            Parse unit parameters
            """
            self._consume("LBRACKET")
            while self._peek().type != "RBRACKET":
                p: dict[str, AstNode] = {}
                p["name"] = self._make_id(self._consume("ID"))
                if self._peek().type in {"ASSIGN", "COMMA"}:
                    self.errors.unexpectedToken(
                        self._peek(), help="Unit parameters must have type annotations"
                    )
                self._consume("COLON")
                p["type"] = self.unit(standalone=True)

                if self._peek().type == "ASSIGN":
                    self._consume("ASSIGN")
                    p["default"] = self._parse_number(self._consume("NUMBER"))

                params.append(
                    Param(
                        name=p["name"],
                        default=p.get("default"),
                        type=None,
                        loc=nodeloc(p["name"], p.get("default", p["name"])),
                    )
                )

                if self._peek().type == "COMMA":
                    self._consume("COMMA")
                else:
                    break

            self._consume("RBRACKET")

        unit = None
        if self._peek().type == "ASSIGN":
            self._consume("ASSIGN")
            self._clear()
            unit = self.unit(standalone=True)

        return UnitDefinition(
            name=self._make_id(name),
            dimension=dimension,
            params=params,
            value=unit,
            loc=nodeloc(start, unit or name),
        )

    def function(self, anonymous=False) -> AstNode:
        name = self._make_id(self._consume("ID")) if not anonymous else None
        return_type = None

        _bang = self._consume("BANG")
        self._consume("LPAREN")

        params = []
        while self._peek().type != "RPAREN":
            p = {}
            p["name"] = self._make_id(self._consume("ID"))

            if self._peek().type == "COLON":
                self._consume("COLON")
                p["type"] = self.unit(standalone=True)

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
        _assign = self._consume("COLON", "ASSIGN")
        if self.tok.type == "COLON":
            return_type = self.unit(standalone=True)
            _assign = self._consume("ASSIGN")

        body = self.block()

        loc = dataclasses.replace(
            nodeloc(name if name is not None else _bang, body),
            checkpoints={"assign": _assign.loc},
        )
        node = Function(
            name=name,
            params=params,
            return_type=return_type,
            body=body,
            loc=loc,
        )
        return node

    def conditional(self, expression: bool = False) -> AstNode:
        _if = self._consume("IF")
        condition = self.expression()
        self._consume("THEN")
        then_branch = self.block() if not expression else self.expression()
        else_branch = None
        if self._peek().type == "ELSE":
            self._consume("ELSE")
            else_branch = self.block() if not expression else self.expression()
        elif expression:
            self.errors.throw(
                uSyntaxError,
                message="Conditional expression must have an else branch",
                loc=nodeloc(_if, then_branch),
            )

        return If(
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
            loc=nodeloc(condition, else_branch if else_branch else then_branch),
        )

    def forloop(self) -> AstNode:
        _for = self._consume("FOR")
        iterators = [self._make_id(self._consume("ID"))]
        while self._peek().type == "COMMA":
            self._consume("COMMA")
            iterators.append(self._make_id(self._consume("ID")))

        self._consume("IN")
        iterable = self.expression()
        self._consume("DO")
        body = self.block()

        return ForLoop(
            iterators=iterators,
            iterable=iterable,
            body=body,
            loc=nodeloc(_for, body),
        )

    def whileloop(self) -> AstNode:
        _while = self._consume("WHILE")
        condition = self.expression()
        self._consume("DO")
        body = self.block()

        return WhileLoop(
            condition=condition,
            body=body,
            loc=nodeloc(_while, body),
        )

    def conversion(self) -> AstNode:
        node = self.logic_or()
        if len(self.tokens) >= 2 and self._peek().type == "CONVERSION":
            op = self._make_op(self._consume("CONVERSION"))
            display_only = self.tok.value.startswith("(")
            unit = self.unit(standalone=True)
            node = Conversion(
                op=op,
                value=node,
                unit=unit,
                display_only=display_only,
                loc=nodeloc(
                    node, unit if not display_only else self._consume("RPAREN")
                ),
            )
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
            self._consume("NOT")
            self.tok.value = "not"
            op = self._make_op(self.tok)
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

        return self.index()

    def index(self) -> AstNode:
        node = self.call()
        if self._peek(ignore_whitespace=False).type == "LBRACKET":
            self._consume("LBRACKET")

            index = []
            while True:
                if self._peek().type == "RBRACKET" or len(index) >= 3:
                    break

                if self._peek().type == "COLON":
                    index.append(None)
                    self._consume("COLON")
                else:
                    index.append(self.expression())

                    if len(index) < 2 and self._peek().type == "COLON":
                        self._consume("COLON")
                    else:
                        pass

            end = self._consume("RBRACKET")

            if len(index) == 1 and index[0] is not None:
                index = index[0]
            else:
                index += [None] * (3 - len(index))
                index = Slice(
                    start=index[0],
                    stop=index[1],
                    step=index[2],
                )
            node = Index(iterable=node, index=index, loc=nodeloc(node, end))
        return node

    def call(self) -> AstNode:
        node = self.range_()
        while self._peek(ignore_whitespace=False).type == "LPAREN":
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

    def range_(self) -> AstNode:
        parts = [self.atom(), None, None]

        i = 1
        while self._peek(ignore_whitespace=False).type == "RANGE" and i < 3:
            self._consume("RANGE")
            parts[i] = self.atom()
            i += 1

        if i == 1:
            return parts[0]
        return Range(
            start=parts[0],
            end=parts[1],
            step=parts[2],
            loc=parts[0].loc.merge(getattr(parts[2], "loc", parts[1].loc)),
        )

    def list(self) -> AstNode:
        start = self.tok
        items = []
        while self._peek().type != "RBRACKET":
            item = self.expression()
            items.append(item)
            if self._peek().type == "RBRACKET":
                break
            self._consume("COMMA")

        end = self._consume("RBRACKET")
        return List(items=items, loc=nodeloc(start, end))

    def tuple(self) -> AstNode:
        """Tuple literal `([...])` or simple `()`"""
        start = self.tok
        self._consume("LBRACKET")

        items = []
        while self._peek().type != "RBRACKET":
            item = self.expression()

            items.append(item)
            if self._peek().type == "RBRACKET":
                break
            self._consume("COMMA")

        self._consume("RBRACKET")
        if self._peek(ignore_whitespace=False).type == "WHITESPACE":
            self._consume("RPAREN")
            return List(items=items, loc=nodeloc(start, self.tok))

        end = self._consume("RPAREN")
        return Tuple(items=items, loc=nodeloc(start, end))

    def unit(self, standalone: bool = False) -> Unit:
        parser = UnitParser(
            tokens=self.tokens, module=self.module, standalone=standalone
        )
        unit = parser.start()
        self.tokens = parser.tokens
        return unit

    def atom(self) -> AstNode:
        tok = self._consume(
            "NUMBER", "TRUE", "FALSE", "ID", "STRING", "LBRACKET", "LPAREN"
        )
        match tok.type:
            case "NUMBER":
                num = self._parse_number(tok)
                if self._peek(ignore_whitespace=False).type in {"LPAREN", "ID"} or (
                    self._peek(2, ignore_whitespace=False).type in {"LPAREN", "ID"}
                    and self._peek(ignore_whitespace=False).value == " "
                ):
                    unit = self.unit()
                    num = dataclasses.replace(num, unit=unit, loc=nodeloc(num, unit))
                return num
            case "TRUE" | "FALSE":
                return Boolean(value=tok.value == "TRUE", loc=tok.loc)
            case "ID":
                return self._make_id(tok)
            case "STRING":
                return String(value=tok.value, loc=tok.loc)
            case "LBRACKET":
                """List literal"""
                return self.list()
            case "LPAREN":
                if self._peek(ignore_whitespace=False).type != "LBRACKET":
                    node = self.expression()
                    self._consume("RPAREN")
                    node = dataclasses.replace(node, loc=nodeloc(node, self.tok))
                    return node
                else:
                    return self.tuple()
            case _:
                raise SyntaxError(f"Unexpected token {tok}")

    def import_stmt(self) -> Import:
        start = self._consume("IMPORT")
        module_name = self._consume("ID")
        module = self._make_id(module_name)

        alias = None
        if self._peek().type == "ID" and self._peek().value == "as":
            self._consume("ID")  # consume 'as'
            alias_name = self._consume("ID")
            alias = self._make_id(alias_name)

        return Import(module=module, alias=alias, loc=nodeloc(start, alias or module))

    def from_import_stmt(self) -> FromImport:
        start = self._consume("FROM")
        module_name = self._consume("ID")
        module = self._make_id(module_name)

        self._consume("IMPORT")

        names = []
        aliases = []

        # Check for 'import *'
        if self._peek().type == "TIMES":
            self._consume("TIMES")
            return FromImport(
                module=module, names=None, aliases=None, loc=nodeloc(start, self.tok)
            )

        i = 0
        atted_until = -1
        while True:
            self._clear()
            if self._peek().type == "AT":
                if atted_until >= i:
                    self.errors.throw(
                        uSyntaxError,
                        "'@' cannot be used within a list of identifiers",
                        loc=self._peek(ignore_whitespace=False).loc,
                    )
                # parse unit namespace references
                self._consume("AT")
                match self._peek(ignore_whitespace=False).type:
                    case "LPAREN":
                        self._consume("LPAREN")
                        atted_until = math.inf
                    case "ID":
                        atted_until = i
                    case _:
                        self.errors.throw(
                            uSyntaxError,
                            "Expected identifier or list of identifiers after '@'",
                            loc=self._peek(ignore_whitespace=False).loc,
                        )

            name_tok = self._consume("ID", ignore_whitespace=False)
            if atted_until >= i:
                name_tok.value = "@" + name_tok.value
            name = self._make_id(name_tok)
            names.append(name)

            alias = None
            if self._peek().type == "ID" and self._peek().value == "as":
                self._consume("ID")  # consume 'as'
                alias_tok = self._consume("ID")
                alias = self._make_id(alias_tok)
            aliases.append(alias)

            if self._peek().type == "RPAREN":
                self._consume("RPAREN")
                atted_until = -1
            if self._peek().type != "COMMA":
                break
            self._consume("COMMA")

            i += 1

        end = aliases[-1] if aliases[-1] else names[-1]
        return FromImport(
            module=module, names=names, aliases=aliases, loc=nodeloc(start, end)
        )
