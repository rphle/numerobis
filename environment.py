import uuid
from difflib import get_close_matches
from typing import Any, Callable, Literal, Optional, overload

from astnodes import AstNode
from typechecker.types import Dimension, T

namespace_names = Literal["names", "dimensions", "units", "imports", "nodes"]


class Namespaces:
    def __init__(
        self,
        names: dict[str, T] | None = None,
        dimensions: dict[str, "Dimension"] | None = None,
        units: dict[str, "Dimension"] | None = None,
        imports: dict[str, "Namespaces"] | None = None,
        nodes: dict[int, AstNode] | None = None,
    ):
        self.names = names or {}
        self.dimensions = dimensions or {}
        self.units = units or {}
        self.imports = imports or {}
        self.nodes = nodes or {}

    def copy(self):
        return Namespaces(
            self.names.copy(),
            self.dimensions.copy(),
            self.units.copy(),
            self.imports.copy(),
            self.nodes.copy(),
        )

    def update(self, other: "Namespaces"):
        self.names.update(other.names)
        self.dimensions.update(other.dimensions)
        self.units.update(other.units)
        self.nodes.update(other.nodes)

    def __call__(self, name: namespace_names) -> dict[str, Any]:
        return getattr(self, name)

    def write(self, name: namespace_names, key: str, value: Any):
        getattr(self, name)[key] = value


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

    def copy(self):
        return Env(
            self.glob,
            self.names.copy(),
            self.dimensions.copy(),
            self.units.copy(),
            self.meta.copy(),
            level=self.level + 1,
        )

    def suggest(self, namespace: namespace_names):
        """Get suggestion for misspelled name"""

        available_keys = getattr(self, namespace).keys()

        def _suggest(name: str) -> str | None:
            matches = get_close_matches(name, available_keys, n=1, cutoff=0.6)
            return matches[0] if matches else None

        return _suggest

    @overload
    def get(self, namespace: Literal["names"]) -> Callable[[str], T]: ...
    @overload
    def get(
        self, namespace: Literal["dimensions", "units"]
    ) -> Callable[[str], Dimension]: ...
    def get(self, namespace: namespace_names) -> Callable[[str], T | Dimension]:
        def _get(name: str) -> T | Dimension:
            return self.glob(namespace)[self(namespace)[name]]

        return _get

    def set(self, namespace: namespace_names):
        def _set(name: str, value: Any, _hash: Optional[str] = None):
            if _hash is None:
                if self.level > 0:
                    _hash = f"{name}-{uuid.uuid4()}"
                else:
                    _hash = name
            self.glob.write(namespace, _hash, value)
            self(namespace)[name] = _hash

        return _set

    def export(self, namespace: namespace_names) -> dict[str, Any]:
        return {name: self.glob(namespace)[name] for name in self(namespace)}

    def __call__(self, namespace: namespace_names) -> dict[str, str]:
        return getattr(self, namespace)

    def __repr__(self):
        return "\n".join(
            f"{name} = {self(name)}"  # type: ignore
            for name in {"names", "dimensions", "units"}
        )
