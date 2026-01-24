import dataclasses
import math

from ..classes import Header, ModuleMeta
from ..nodes.ast import (
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
    ExternDeclaration,
    Float,
    ForLoop,
    FromImport,
    Function,
    FunctionAnnotation,
    Identifier,
    If,
    Import,
    Index,
    IndexAssignment,
    Integer,
    List,
    Param,
    Range,
    Return,
    Slice,
    String,
    Tuple,
    Type,
    UnaryOp,
    UnitDefinition,
    UnitReference,
    Variable,
    VariableDeclaration,
    WhileLoop,
)
from ..nodes.core import Location, Token, nodeloc
from ..nodes.unit import Expression, One
from ..typechecker.operators import typetable
from .template import ParserTemplate
from .units.unitparser import UnitParser, UnitParserConfig


class Parser(ParserTemplate):
    def __init__(self, tokens: list[Token], module: ModuleMeta):
        super().__init__(tokens=tokens, module=module)
        # flag becomes False as soon as a non-import statement is encountered
        self.imports_allowed = True
        self.header = Header()

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

        if self.imports_allowed and first.type not in [
            "IMPORT",
            "FROM",
            "UNIT",
            "DIMENSION",
        ]:
            self.imports_allowed = False

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
        elif first.type == "EXTERN":
            """Extern declaration"""
            return self.extern_declaration()
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

        return self.index_assignment()

    def index_assignment(self):
        left = self.expression()

        if self._peek().type == "ASSIGN":
            self._consume("ASSIGN")
            value = self.expression()

            if not isinstance(left, Index):
                self.errors.throw(21, loc=left.loc)
                raise

            return IndexAssignment(
                target=left, value=value, loc=left.loc.merge(value.loc)
            )

        return left

    def expression(self) -> AstNode:
        first = self._peek()
        if first.type == "IF":
            """Conditional expression"""
            return self.conditional(expression=True)
        elif first.type == "AT":
            """Reference unit namespace"""
            if self._peek(2, ignore_whitespace=False).type not in {"LPAREN", "ID"}:
                self.errors.throw(
                    3,
                    loc=Location(line=first.loc.line, col=first.loc.col + 1),
                )
            self._consume("AT")
            return UnitReference(unit=self.unit())
        elif self._peek().type == "BANG":
            return self.function(anonymous=True)
        elif first.type == "ID" and self._peek(2).type == "BANG":
            # Named function as expression is not allowed
            self.errors.throw(
                19,
                loc=first.loc.merge(self._peek(2).loc),
            )

        return self.range_()

    def variable(self, declaration: bool = False) -> AstNode:
        name = self._consume("ID")
        type_token = None
        if declaration or self._peek().type == "COLON":
            self._consume("COLON")
            type_token = self.type()

        if declaration or (self._peek().type != "ASSIGN" and type_token is not None):
            assert type_token is not None
            return VariableDeclaration(
                name=Identifier(name=name.value, loc=name.loc),
                type=type_token,
                loc=nodeloc(name, type_token),
            )

        self._consume("ASSIGN")
        expr = self.expression()

        return Variable(
            name=Identifier(name=name.value, loc=name.loc),
            value=expr,
            type=type_token if type_token else None,
            loc=nodeloc(name, expr),
        )

    def dimension_def(self) -> AstNode:
        start = self._consume("DIMENSION")
        name = self._consume("ID")

        if not self.imports_allowed:
            self.errors.throw(20, statement="dimension definitions", loc=start.loc)

        value = None
        if self._peek().type == "ASSIGN":
            self._consume("ASSIGN")
            self._clear()
            value = self.unit(standalone=True, constants=True, scalars=True)

        node = DimensionDefinition(
            name=self._make_id(name),
            value=value,
            loc=nodeloc(start, value or name),
        )
        self.header.dimensions.append(node)
        return node

    def unit_def(self) -> AstNode:
        start = self._consume("UNIT")
        name = self._consume("ID")

        if not self.imports_allowed:
            self.errors.throw(20, statement="unit definitions", loc=start.loc)

        dimension = None
        if self._peek().type == "COLON":
            self._consume("COLON")
            if self._peek().type == "ID":
                dimension = self._make_id(self._consume("ID"))
            elif self._peek().type == "NUMBER" and self._peek().value == "1":
                self._consume("NUMBER")
                dimension = Identifier(name="1", loc=self.tok.loc)
            else:
                self.errors.throw(
                    1,
                    token=self._peek().value,
                    loc=self._peek().loc,
                    help="Expected dimension",
                )

        params = []
        if self._peek().type == "LPAREN":
            self.errors.throw(5, token=self._peek().value, loc=self._peek().loc)
        if self._peek().type == "LBRACKET":
            """
            Parse unit parameters
            """
            self._consume("LBRACKET")
            while self._peek().type != "RBRACKET":
                p = {}
                p["name"] = self._make_id(self._consume("ID"))
                if self._peek().type in {"ASSIGN", "COMMA"}:
                    self.errors.throw(6, loc=self._peek().loc)
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
            unit = self.unit(
                standalone=True,
                calls=True,
                unitful_numbers=True,
                constants=True,
                addition=True,
                scalars=True,
            )

        node = UnitDefinition(
            name=self._make_id(name),
            dimension=dimension,
            params=params,
            value=unit,
            loc=nodeloc(start, unit or name),
        )
        self.header.units.append(node)
        return node

    def function(self, anonymous=False, body=True) -> AstNode:
        name = self._make_id(self._consume("ID")) if not anonymous or not body else None
        return_type = None

        _bang = self._consume("BANG")
        self._consume("LPAREN")

        params = []
        while self._peek().type != "RPAREN":
            p = {}
            p["name"] = self._make_id(self._consume("ID"))

            if self._peek().type == "COLON":
                self._consume("COLON")
                p["type"] = self.type()

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

        _rparen = self._consume("RPAREN")
        _assign = self._consume("COLON", "ASSIGN" if body else "/")
        if self.tok.type == "COLON":
            return_type = self.type()
            if body:
                _assign = self._consume("ASSIGN")

        body = self.block() if body else None

        loc = dataclasses.replace(
            nodeloc(
                name if name is not None else _bang,
                body if body else (return_type if return_type else _rparen),
            ),
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
            self.errors.throw(14, loc=nodeloc(_if, then_branch))

        return If(
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
            expression=expression,
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

    def range_(self) -> AstNode:
        parts = [self.conversion(), None, None]

        i = 1
        while self._peek(ignore_whitespace=False).type == "RANGE" and i < 3:
            self._consume("RANGE")
            parts[i] = self.conversion()
            i += 1

        if i == 1:
            return parts[0]
        return Range(
            start=parts[0],
            end=parts[1],
            step=parts[2],
            loc=parts[0].loc.merge(getattr(parts[2], "loc", parts[1].loc)),
        )

    def conversion(self) -> AstNode:
        node = self.logic_or()
        if len(self.tokens) >= 2 and self._peek().type == "CONVERSION":
            op = self._make_op(self._consume("CONVERSION"))
            display_only = self.tok.value.startswith("(")
            target = self.type()

            if isinstance(target, FunctionAnnotation):
                self.errors.throw(538)
                raise

            node = Conversion(
                op=op,
                value=node,
                target=target,
                display_only=display_only,
                loc=nodeloc(
                    node, target if not display_only else self._consume("RPAREN")
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
        return self._bin_chain(self.term, {"PLUS", "MINUS", "DPLUS", "DMINUS"})

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
                ops.append(self._consume())

            operand = self.postfix()

            if sum(1 for op in ops if op.type == "MINUS") % 2 == 1:
                op = self._make_op(next(op for op in ops if op.type == "MINUS"))
                return UnaryOp(op=op, operand=operand, loc=nodeloc(op, operand))
            return operand

        return self.postfix()

    def call(self, node: AstNode) -> AstNode:
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
                    name=name,
                    value=arg,
                    loc=nodeloc(name if name else arg, arg),
                )
            )
            if self._peek().type == "RPAREN":
                break
            self._consume("COMMA")
        _end = self._consume("RPAREN")
        return Call(callee=node, args=args, loc=nodeloc(node, _end))

    def index(self, node: AstNode) -> AstNode:
        self._consume("LBRACKET")
        parts = []
        colon_count = 0

        while self._peek().type != "RBRACKET":
            if self._peek().type == "COLON":
                if colon_count >= 2:
                    break
                parts.append(None)
                self._consume("COLON")
                colon_count += 1
            else:
                parts.append(self.expression())

                if self._peek().type == "COLON":
                    if colon_count >= 2:
                        break
                    self._consume("COLON")
                    colon_count += 1

        _end = self._consume("RBRACKET")

        if colon_count == 0:
            idx = parts[0]
        else:
            parts += [None] * (3 - len(parts))
            idx = Slice(start=parts[0], stop=parts[1], step=parts[2])

        node = Index(iterable=node, index=idx, loc=nodeloc(node, _end))
        return node

    def postfix(self) -> AstNode:
        """
        Postfix chaining for calls and indexing/slices.
        Starts from `range_()` (preserves range precedence) then repeatedly
        applies `( ... )` or `[ ... ]` as long as either appears immediately after.
        """
        node = self.atom()
        while self._peek(ignore_whitespace=False).type in {"LPAREN", "LBRACKET"}:
            if self._peek(ignore_whitespace=False).type == "LPAREN":
                node = self.call(node)
            else:
                node = self.index(node)

        return node

    def list_(self) -> AstNode:
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

    def tuple_(self) -> AstNode:
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

    def unit(
        self,
        standalone: bool = False,
        calls: bool = False,
        unitful_numbers: bool = False,
        constants: bool = False,
        addition: bool = False,
        scalars: bool = False,
    ) -> Expression | One:
        config = UnitParserConfig(
            standalone=standalone,
            calls=calls,
            unitful_numbers=unitful_numbers,
            constants=constants,
            addition=addition,
            scalars=scalars,
        )
        parser = UnitParser(tokens=self.tokens, module=self.module, config=config)
        unit = parser.start()
        self.tokens = parser.tokens
        return unit if unit else One()

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
                return Boolean(value=tok.value == "true", loc=tok.loc)
            case "ID":
                return self._make_id(tok)
            case "STRING":
                return String(value=tok.value, loc=tok.loc)
            case "LBRACKET":
                """List literal"""
                return self.list_()
            case "LPAREN":
                if self._peek(ignore_whitespace=False).type != "LBRACKET":
                    node = self.expression()
                    self._consume("RPAREN")
                    node = dataclasses.replace(node, loc=nodeloc(node, self.tok))
                    return node
                else:
                    return self.tuple_()
            case _:
                raise SyntaxError(f"Unexpected token {tok}")

    def import_stmt(self) -> Import:
        start = self._consume("IMPORT")
        if not self.imports_allowed:
            self.errors.throw(801, loc=start.loc)

        module_name = self._consume("ID")
        module = self._make_id(module_name)

        alias = None
        if self._peek().type == "ID" and self._peek().value == "as":
            self._consume("ID")  # consume 'as'
            alias_name = self._consume("ID")
            alias = self._make_id(alias_name)

        node = Import(module=module, alias=alias, loc=nodeloc(start, alias or module))
        self.header.imports.append(node)
        return node

    def from_import_stmt(self) -> FromImport:
        start = self._consume("FROM")
        if not self.imports_allowed:
            self.errors.throw(801, loc=start.loc)

        module_name = self._consume("ID")
        module = self._make_id(module_name)

        self._consume("IMPORT")

        names = []
        aliases = []

        # Check for 'import *'
        if self._peek().type == "TIMES":
            self._consume("TIMES")
            node = FromImport(
                module=module, names=None, aliases=None, loc=nodeloc(start, self.tok)
            )
            self.header.imports.append(node)
            return node

        i = 0
        atted_until = -1
        while True:
            self._clear()
            if self._peek().type == "AT":
                if atted_until >= i:
                    self.errors.throw(15, loc=self._peek(ignore_whitespace=False).loc)
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
                            14, loc=self._peek(ignore_whitespace=False).loc
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

        node = FromImport(
            module=module, names=names, aliases=aliases, loc=nodeloc(start, end)
        )
        self.header.imports.append(node)
        return node

    def extern_declaration(self) -> ExternDeclaration:
        _start = self._consume("EXTERN")

        if self._peek(2).type == "BANG":
            value = self.function(body=False)
        else:
            value = self.variable(declaration=True)

        assert isinstance(value, (Function, VariableDeclaration))
        return ExternDeclaration(value=value, loc=nodeloc(_start, value))

    def type(self) -> Type | FunctionAnnotation | Expression | One:
        if self._peek().type == "BANG":
            return self.function_annotation()
        elif self._peek().type == "ID" and self._peek().value in list(typetable.keys()):
            token = self._consume("ID")
            name = Identifier(name=token.value, loc=token.loc)
            if self._peek(ignore_whitespace=True).type == "LBRACKET":
                if name.name in ["Int", "Float", "List"]:
                    self._consume("LBRACKET")
                    param = self.type()
                    self._consume("RBRACKET")
                    return Type(name=name, param=param, loc=name.loc.merge(param.loc))
                else:
                    self.errors.unexpectedToken(
                        self._peek(ignore_whitespace=True),
                        help=f"Type '{name.name}' cannot be parameterized",
                    )
                    raise
            else:
                return Type(name=name, param=None, loc=name.loc)
        else:
            return self.unit(standalone=True)

    def function_annotation(self):
        _bang = self._consume("BANG")
        self._consume("LBRACKET")
        self._consume("LBRACKET")

        params = []
        param_names = []
        arity = [0]
        while self._peek().type != "RBRACKET":
            if self._peek().type == "DIVIDE" and len(arity) == 1:
                # start optional args section
                self._consume("DIVIDE")
                arity.append(arity[0])
            else:
                param_names.append(self._make_id(self._consume("ID")))
                if self._peek().type != "COLON":
                    self.errors.throw(18, self._peek().loc)
                self._consume("COLON")
                params.append(self.type())
                arity[-1] += 1

            if self._peek().type != "RBRACKET":
                self._consume("COMMA")

        self._consume("RBRACKET")
        self._consume("COMMA")

        return_type = self.type()
        _end = self._consume("RBRACKET")

        if len(arity) == 1:
            arity.append(arity[0])

        return FunctionAnnotation(
            params=params,
            param_names=param_names,
            return_type=return_type,
            arity=tuple(arity),  # type: ignore
            loc=_bang.loc.merge(_end.loc),
        )

    def _parse_number(self, token: Token) -> Float | Integer:
        split = token.value.lower().split("e")
        number = split[0].replace("_", "")
        exponent = split[1] if len(split) > 1 else ""
        if "." in exponent:
            self.errors.throw(7, token=token.value, loc=token.loc)

        unit = self._make_unit()
        if "." in number or exponent.startswith("-"):
            return Float(value=number, exponent=exponent, unit=unit, loc=token.loc)
        else:
            return Integer(value=number, exponent=exponent, unit=unit, loc=token.loc)
