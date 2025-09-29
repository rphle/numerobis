import dataclasses
from parser.template import ParserTemplate
from parser.unitparser import UnitParser

from astnodes import (
    Assign,
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
    Function,
    Identifier,
    If,
    Index,
    List,
    Location,
    Param,
    Return,
    Slice,
    String,
    Token,
    Tuple,
    UnaryOp,
    Unit,
    UnitDefinition,
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
            return self.assignment()
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
        elif (
            first.type == "ID"
            and self._peek(2).type == "LPAREN"
            and self._check_function(start=3)
        ):
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
            return Return(value=self.expression(), loc=ret.loc)

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

        return self.conversion()

    def assignment(self) -> AstNode:
        name = self._consume("ID")
        type_token = None
        if self._peek().type == "COLON":
            self._consume("COLON")
            type_token = self.unit(standalone=True)

        self._consume("ASSIGN")
        expr = self.block()

        return Assign(
            target=Identifier(name=name.value, loc=name.loc),
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

    def function(self) -> AstNode:
        name = self._make_id(self._consume("ID"))
        return_type = None

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
        self._consume("COLON", "ASSIGN")
        if self.tok.type == "COLON":
            return_type = self.unit(standalone=True)
            self._consume("ASSIGN")

        body = self.block()

        node = Function(
            name=name,
            params=params,
            return_type=return_type,
            body=body,
            loc=nodeloc(name, body),
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
        var = self._make_id(self._consume("ID"))
        self._consume("IN")
        iterable = self.expression()
        self._consume("DO")
        body = self.block()
        return ForLoop(
            var=var,
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
        if self._peek().type in {"NOT", "NOTBANG"}:
            self._consume("NOT", "NOTBANG")
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
        node = self.atom()
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
                    num = dataclasses.replace(num, unit=self.unit())
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
                    return node
                else:
                    return self.tuple()
            case _:
                raise SyntaxError(f"Unexpected token {tok}")

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
                self.errors.unexpectedEOF()
            i += 1
