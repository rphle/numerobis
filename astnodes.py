from dataclasses import dataclass, field


@dataclass
class Location:
    line: int = -1
    col: int = -1
    start: int = -1
    span: int = 0


@dataclass
class Token:
    type: str
    value: str
    loc: Location = field(default_factory=lambda: Location(), repr=False)

    def __bool__(self):
        return True


@dataclass(kw_only=True)
class AstNode:
    loc: Location = field(default_factory=lambda: Location(), repr=False)

    def __bool__(self):
        return True


@dataclass(kw_only=True)
class Block(AstNode):
    body: list[AstNode]


@dataclass(kw_only=True)
class Identifier(AstNode):
    name: str


@dataclass(kw_only=True)
class Unit(AstNode):
    unit: AstNode


@dataclass(kw_only=True)
class If(AstNode):
    condition: AstNode
    then_branch: AstNode
    else_branch: AstNode | None = None


@dataclass(kw_only=True)
class Boolean(AstNode):
    value: bool


@dataclass(kw_only=True)
class Integer(AstNode):
    value: str
    exponent: str
    unit: Unit | None


@dataclass(kw_only=True)
class Float(AstNode):
    value: str
    exponent: str
    unit: Unit | None


@dataclass(kw_only=True)
class String(AstNode):
    value: str


@dataclass(kw_only=True)
class List(AstNode):
    items: list[AstNode]


@dataclass(kw_only=True)
class Tuple(AstNode):
    items: list[AstNode]


@dataclass(kw_only=True)
class Operator(AstNode):
    name: str


@dataclass(kw_only=True)
class UnaryOp(AstNode):
    op: Operator
    operand: AstNode


@dataclass(kw_only=True)
class BinOp(AstNode):
    op: Operator
    left: AstNode
    right: AstNode


@dataclass(kw_only=True)
class BoolOp(AstNode):
    op: Operator
    left: AstNode
    right: AstNode


@dataclass(kw_only=True)
class Compare(AstNode):
    ops: list[Operator]
    left: AstNode
    comparators: list[AstNode]


@dataclass(kw_only=True)
class Conversion(AstNode):
    op: Operator
    value: AstNode
    unit: Unit
    display_only: bool = False


@dataclass(kw_only=True)
class Assign(AstNode):
    target: AstNode
    type: Unit | None
    value: AstNode


@dataclass(kw_only=True)
class ForLoop(AstNode):
    var: Identifier
    iterable: AstNode
    body: AstNode


@dataclass(kw_only=True)
class WhileLoop(AstNode):
    condition: AstNode
    body: AstNode


@dataclass(kw_only=True)
class UnitDeclaration(AstNode):
    name: Identifier
    params: list["Param"]
    value: Unit


@dataclass(kw_only=True)
class Param(AstNode):
    name: Identifier
    type: Unit | None
    default: AstNode | None


@dataclass(kw_only=True)
class Function(AstNode):
    name: Identifier
    params: list[Param]
    return_type: Unit | None
    body: AstNode


@dataclass(kw_only=True)
class CallArg(AstNode):
    name: Identifier | None
    value: AstNode


@dataclass(kw_only=True)
class Call(AstNode):
    callee: AstNode
    args: list[CallArg]


@dataclass(kw_only=True)
class Index(AstNode):
    iterable: AstNode
    index: AstNode


@dataclass(kw_only=True)
class Slice(AstNode):
    start: AstNode
    stop: AstNode | None
    step: AstNode


@dataclass(kw_only=True)
class Break(AstNode):
    pass


@dataclass(kw_only=True)
class Continue(AstNode):
    pass


@dataclass(kw_only=True)
class Return(AstNode):
    value: AstNode | None
