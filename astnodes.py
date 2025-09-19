from dataclasses import dataclass, field

from classes import Location, Token


@dataclass(kw_only=True)
class AstNode:
    loc: Location = field(default_factory=lambda: Location(), repr=False)

    def __bool__(self):
        return True


@dataclass(kw_only=True)
class Integer(AstNode):
    value: str


@dataclass(kw_only=True)
class Float(AstNode):
    value: str


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
    right: list[AstNode]
