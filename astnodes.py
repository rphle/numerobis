from dataclasses import dataclass, field

from classes import Location, Token


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


@dataclass(kw_only=True)
class Float(AstNode):
    value: str
    exponent: str


@dataclass(kw_only=True)
class BinOp(AstNode):
    op: Token
    left: AstNode
    right: AstNode


@dataclass(kw_only=True)
class BoolOp(AstNode):
    op: Token
    left: AstNode
    right: AstNode


@dataclass(kw_only=True)
class Compare(AstNode):
    ops: list[Token]
    left: AstNode
    comparators: list[AstNode]


@dataclass(kw_only=True)
class Assign(AstNode):
    target: AstNode
    type: Identifier | None
    value: AstNode
