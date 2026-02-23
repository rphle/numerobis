"""AST node definitions for language constructs."""

from dataclasses import dataclass
from typing import Optional

from .core import AstNode, Identifier
from .unit import Expression, One


@dataclass(kw_only=True, frozen=True)
class Block(AstNode):
    body: list[AstNode]


@dataclass(kw_only=True, frozen=True)
class UnitReference(AstNode):
    unit: Expression | One


@dataclass(kw_only=True, frozen=True)
class If(AstNode):
    condition: AstNode
    then_branch: AstNode
    else_branch: AstNode | None = None
    expression: bool = False


@dataclass(kw_only=True, frozen=True)
class Boolean(AstNode):
    value: bool


@dataclass(kw_only=True, frozen=True)
class Integer(AstNode):
    value: str
    exponent: str
    unit: Expression


@dataclass(kw_only=True, frozen=True)
class Float(AstNode):
    value: str
    exponent: str
    unit: Expression


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
    target: "Type | Expression | One"
    display_only: bool = False


@dataclass(kw_only=True, frozen=True)
class Variable(AstNode):
    name: Identifier
    type: Optional["Type | FunctionAnnotation | Expression | One"]
    value: AstNode


@dataclass(kw_only=True, frozen=True)
class VariableDeclaration(AstNode):
    name: Identifier
    type: "Type | FunctionAnnotation | Expression | One"


@dataclass(kw_only=True, frozen=True)
class ForLoop(AstNode):
    iterators: list[Identifier]
    iterable: AstNode
    body: AstNode


@dataclass(kw_only=True, frozen=True)
class WhileLoop(AstNode):
    condition: AstNode
    body: AstNode


@dataclass(kw_only=True, frozen=True)
class Range(AstNode):
    start: AstNode
    end: AstNode
    step: AstNode | None


@dataclass(kw_only=True, frozen=True)
class UnitDefinition(AstNode):
    name: Identifier
    dimension: Identifier | None
    params: list["Param"]
    value: Expression | One | None


@dataclass(kw_only=True, frozen=True)
class DimensionDefinition(AstNode):
    name: Identifier
    value: Expression | One | None = None


@dataclass(kw_only=True, frozen=True)
class Param(AstNode):
    name: Identifier
    type: Optional["Type | FunctionAnnotation | Expression | One"]
    default: AstNode | None


@dataclass(kw_only=True, frozen=True)
class Function(AstNode):
    name: Identifier | None
    params: list[Param]
    return_type: Optional["Type | FunctionAnnotation | Expression | One"]
    body: Optional[AstNode]


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
class IndexAssignment(AstNode):
    target: Index
    value: AstNode


@dataclass(kw_only=True, frozen=True)
class Break(AstNode):
    pass


@dataclass(kw_only=True, frozen=True)
class Continue(AstNode):
    pass


@dataclass(kw_only=True, frozen=True)
class Return(AstNode):
    value: AstNode | None


@dataclass(kw_only=True, frozen=True)
class Import(AstNode):
    module: Identifier
    alias: Identifier | None = None


@dataclass(kw_only=True, frozen=True)
class FromImport(AstNode):
    module: Identifier
    names: list[Identifier] | None = None  # None means import *
    aliases: list[Identifier | None] | None = None


@dataclass(kw_only=True, frozen=True)
class Type(AstNode):
    name: Identifier
    param: Optional["Type | FunctionAnnotation | Expression | One"]


@dataclass(kw_only=True, frozen=True)
class FunctionAnnotation(AstNode):
    params: list[Expression]
    param_names: list[Identifier]
    return_type: Optional["Type | FunctionAnnotation | Expression | One"]
    arity: tuple[int, int]


@dataclass(kw_only=True, frozen=True)
class ExternDeclaration(AstNode):
    value: VariableDeclaration | Function
