from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .nodes.ast import DimensionDefinition, FromImport, Import, UnitDefinition


@dataclass
class ModuleMeta:
    path: Path
    source: str


@dataclass
class Header:
    imports: list[Import | FromImport] = field(default_factory=list)
    units: list[UnitDefinition] = field(default_factory=list)
    dimensions: list[DimensionDefinition] = field(default_factory=list)

    def merge(self, other: "Header") -> "Header":
        return Header(
            imports=self.imports + other.imports,
            units=self.units + other.units,
            dimensions=self.dimensions + other.dimensions,
        )


@dataclass
class CompiledUnits:
    units: dict[str, str] = field(default_factory=dict)
    inverted: dict[str, str] = field(default_factory=dict)
    bases: dict[str, str] = field(default_factory=dict)
    logarithmic: set[str] = field(default_factory=set)


@dataclass
class CompiledModule:
    meta: ModuleMeta
    imports: list[str]
    include: set[str]
    code: str
    functions: list[str]
    typedefs: list[str]
    units: CompiledUnits
    namespaces: Optional["Namespaces"] = None  # type: ignore # noqa
