from dataclasses import dataclass, field


def nodeloc(*nodes: "Token | AstNode"):
    return Location(
        line=nodes[0].loc.line,
        col=nodes[0].loc.col,
        start=nodes[0].loc.start,
        end_line=nodes[-1].loc.end_line,
        end_col=nodes[-1].loc.end_col,
    )


@dataclass
class Location:
    line: int = -1
    col: int = -1
    start: int = -1
    end_line: int = -1
    end_col: int = -1

    def split(self) -> list["Location"]:
        """
        Split a multi-line position span into individual line positions.
        """
        return [
            Location(
                line=line,
                col=self.col if line == self.line else 1,
                end_line=line,
                end_col=-1 if line != self.end_line else self.end_col,
            )
            for line in range(self.line, self.end_line + 1)
        ]


@dataclass
class Token:
    type: str
    value: str
    loc: Location = field(default_factory=lambda: Location(), repr=False, compare=False)

    def __bool__(self):
        return True


@dataclass(kw_only=True, frozen=True)
class AstNode:
    loc: Location = field(default_factory=lambda: Location(), repr=False, compare=False)

    def __bool__(self):
        return True


@dataclass(kw_only=True, frozen=True)
class Block(AstNode):
    body: list[AstNode]


@dataclass(kw_only=True, frozen=True)
class Identifier(AstNode):
    name: str


@dataclass(kw_only=True, frozen=True)
class Unit(AstNode):
    unit: list["AstNode | Unit"]


@dataclass(kw_only=True, frozen=True)
class If(AstNode):
    condition: AstNode
    then_branch: AstNode
    else_branch: AstNode | None = None


@dataclass(kw_only=True, frozen=True)
class Boolean(AstNode):
    value: bool


@dataclass(kw_only=True, frozen=True)
class Scalar(AstNode):
    value: str
    exponent: str


@dataclass(kw_only=True, frozen=True)
class Integer(AstNode):
    value: str
    exponent: str
    unit: Unit | None


@dataclass(kw_only=True, frozen=True)
class Float(AstNode):
    value: str
    exponent: str
    unit: Unit | None


@dataclass(kw_only=True, frozen=True)
class String(AstNode):
    value: str


@dataclass(kw_only=True, frozen=True)
class List(AstNode):
    items: list[AstNode]


@dataclass(kw_only=True, frozen=True)
class Tuple(AstNode):
    items: list[AstNode]


@dataclass(kw_only=True, frozen=True)
class Operator(AstNode):
    name: str


@dataclass(kw_only=True, frozen=True)
class UnaryOp(AstNode):
    op: Operator
    operand: AstNode


@dataclass(kw_only=True, frozen=True)
class BinOp(AstNode):
    op: Operator
    left: AstNode
    right: AstNode


@dataclass(kw_only=True, frozen=True)
class BoolOp(AstNode):
    op: Operator
    left: AstNode
    right: AstNode


@dataclass(kw_only=True, frozen=True)
class Compare(AstNode):
    ops: list[Operator]
    left: AstNode
    comparators: list[AstNode]


@dataclass(kw_only=True, frozen=True)
class Conversion(AstNode):
    op: Operator
    value: AstNode
    unit: Unit
    display_only: bool = False


@dataclass(kw_only=True, frozen=True)
class Assign(AstNode):
    target: AstNode
    type: Unit | None
    value: AstNode


@dataclass(kw_only=True, frozen=True)
class ForLoop(AstNode):
    var: Identifier
    iterable: AstNode
    body: AstNode


@dataclass(kw_only=True, frozen=True)
class WhileLoop(AstNode):
    condition: AstNode
    body: AstNode


@dataclass(kw_only=True, frozen=True)
class UnitDefinition(AstNode):
    name: Identifier
    dimension: Identifier | None
    params: list["Param"]
    value: Unit | None


@dataclass(kw_only=True, frozen=True)
class DimensionDefinition(AstNode):
    name: Identifier
    value: Unit | None = None


@dataclass(kw_only=True, frozen=True)
class Param(AstNode):
    name: Identifier
    type: Unit | None
    default: AstNode | None


@dataclass(kw_only=True, frozen=True)
class Function(AstNode):
    name: Identifier
    params: list[Param]
    return_type: Unit | None
    body: AstNode


@dataclass(kw_only=True, frozen=True)
class CallArg(AstNode):
    name: Identifier | None
    value: AstNode


@dataclass(kw_only=True, frozen=True)
class Call(AstNode):
    callee: AstNode
    args: list[CallArg]


@dataclass(kw_only=True, frozen=True)
class Index(AstNode):
    iterable: AstNode
    index: AstNode


@dataclass(kw_only=True, frozen=True)
class Slice(AstNode):
    start: AstNode
    stop: AstNode | None
    step: AstNode


@dataclass(kw_only=True, frozen=True)
class Break(AstNode):
    pass


@dataclass(kw_only=True, frozen=True)
class Continue(AstNode):
    pass


@dataclass(kw_only=True, frozen=True)
class Return(AstNode):
    value: AstNode | None
