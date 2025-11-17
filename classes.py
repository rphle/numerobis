import dataclasses
from dataclasses import dataclass
from pathlib import Path

from astnodes import AstNode


@dataclass
class ModuleMeta:
    path: Path
    source: str


@dataclasses.dataclass(kw_only=True, frozen=True)
class E:
    base: "AstNode | list | E"
    exponent: float
