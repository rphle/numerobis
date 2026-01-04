from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from nodes.ast import DimensionDefinition, FromImport, Import, UnitDefinition


@dataclass
class ModuleMeta:
    path: Path
    source: str


@dataclass
class Header:
    imports: list[Import | FromImport] = field(default_factory=list)
    units: list[UnitDefinition] = field(default_factory=list)
    dimensions: list[DimensionDefinition] = field(default_factory=list)


@dataclass
class CompiledModule:
    meta: ModuleMeta
    imports: list[str]
    include: set[str]
    code: str
    namespaces: Optional["Namespaces"] = None  # type: ignore # noqa
