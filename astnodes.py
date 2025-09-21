from dataclasses import dataclass, field

from classes import Location


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
    unit: list[AstNode]


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
    type: Identifier | None
    value: AstNode


@dataclass(kw_only=True)
class ForLoop(AstNode):
    var: Identifier
    iterable: AstNode
    body: AstNode


@dataclass(kw_only=True)
class UnitDeclaration(AstNode):
    name: Identifier
    unit: Unit


@dataclass(kw_only=True)
class Param(AstNode):
    name: Identifier
    type: Identifier | None
    default: AstNode


@dataclass(kw_only=True)
class Function(AstNode):
    name: Identifier
    params: list[Param]
    return_type: Identifier | None
    body: AstNode


@dataclass(kw_only=True)
class CallArg(AstNode):
    name: Identifier | None
    value: AstNode


@dataclass(kw_only=True)
class Call(AstNode):
    callee: AstNode
    args: list[CallArg]
