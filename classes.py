from dataclasses import dataclass, field
from pathlib import Path

from nodes.ast import AstNode, DimensionDefinition, FromImport, Import, UnitDefinition


@dataclass
class ModuleMeta:
    path: Path
    source: str


@dataclass(kw_only=True, frozen=True)
class E:
    base: "AstNode | list | E"
    exponent: float


@dataclass
class Header:
    imports: list[Import | FromImport] = field(default_factory=list)
    units: list[UnitDefinition] = field(default_factory=list)
    dimensions: list[DimensionDefinition] = field(default_factory=list)
