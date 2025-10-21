import dataclasses
import uuid
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path
from typing import Any, Literal

from astnodes import AstNode
from typechecker.types import NodeType


@dataclass
class ModuleMeta:
    path: Path
    source: str


@dataclasses.dataclass(kw_only=True, frozen=True)
class E:
    base: "AstNode | list | E"
    exponent: float


@dataclasses.dataclass(kw_only=True, frozen=True)
class Namespaces:
    names: dict[str, NodeType] = dataclasses.field(default_factory=dict)
    dimensions: dict[str, NodeType] = dataclasses.field(default_factory=dict)
    units: dict[str, NodeType] = dataclasses.field(default_factory=dict)
    imports: dict[str, "Namespaces"] = dataclasses.field(default_factory=dict)

    def update(self, other: "Namespaces"):
        self.names.update(other.names)
        self.dimensions.update(other.dimensions)
        self.units.update(other.units)

    def __call__(self, name: str) -> dict[str, NodeType]:
        return getattr(self, name)


class Env:
    def __init__(
        self,
        glob: Namespaces,
        names: dict = {},
        dimensions: dict = {},
        units: dict = {},
        meta: dict = {},
        level: int = -1,
    ):
        self.glob: Namespaces = glob

        self.names: dict[str, str] = names
        self.dimensions: dict[str, str] = dimensions
        self.units: dict[str, str] = units
        self.meta: dict[str, Any] = meta

        self.level = level

    def _(self):
        return Env(
            self.glob,
            self.names,
            self.dimensions,
            self.units,
            self.meta,
            level=self.level + 1,
        )

    def suggest(self, namespace: Literal["names", "dimensions", "units"]):
        """Get suggestion for misspelled name"""

        available_keys = getattr(self, namespace).keys()

        def _suggest(name: str) -> str | None:
            matches = get_close_matches(name, available_keys, n=1, cutoff=0.6)
            return matches[0] if matches else None

        return _suggest

    def get(self, namespace: Literal["names", "dimensions", "units"]):
        def _get(name: str) -> NodeType:
            return self.glob(namespace)[self(namespace)[name]]

        return _get

    def set(self, namespace: Literal["names", "dimensions", "units"]):
        def _set(name: str, value: Any):
            if self.level > 0:
                _hash = f"{name}-{uuid.uuid1()}"
            else:
                _hash = name
            self.glob(namespace)[_hash] = value
            self(namespace)[name] = _hash

        return _set

    def export(self, namespace: str) -> dict[str, NodeType]:
        return {name: self.glob(namespace)[name] for name in self(namespace)}

    def __call__(self, namespace: str) -> dict[str, str]:
        return getattr(self, namespace)

    def __repr__(self):
        return "\n".join(
            f"{name} = {self(name)}" for name in {"names", "dimensions", "units"}
        )
