import uuid
from difflib import get_close_matches
from typing import Any, Callable, Literal, Optional, overload

from nodes.core import AstNode
from nodes.unit import Expression, One
from typechecker.types import T

namespace_names = Literal["names", "dimensions", "units", "imports", "nodes", "typed"]


class Namespaces:
    def __init__(
        self,
        names: dict[str, T] | None = None,
        dimensions: dict[str, Expression | One | None] | None = None,
        units: dict[str, Expression | One | None] | None = None,
        imports: dict[str, "Namespaces"] | None = None,
        nodes: dict[int, AstNode] | None = None,
        typed: dict[int, str] | None = None,
    ):
        self.names = names or {}
        self.dimensions = dimensions or {}
        self.units = units or {}
        self.imports = imports or {}
        self.nodes = nodes or {}
        self.typed = typed or {}

    def copy(self):
        return Namespaces(
            self.names.copy(),
            self.dimensions.copy(),
            self.units.copy(),
            self.imports.copy(),
            self.nodes.copy(),
            self.typed.copy(),
        )

    def update(self, other: "Namespaces"):
        self.names.update(other.names)
        self.dimensions.update(other.dimensions)
        self.units.update(other.units)
        self.nodes.update(other.nodes)
        self.typed.update(other.typed)

    def __call__(self, name: namespace_names) -> dict[str, Any]:
        return getattr(self, name)

    def write(self, name: namespace_names, key: str, value: Any):
        getattr(self, name)[key] = value

    def suggest(self, namespace: namespace_names, name: str):
        """Get suggestion for misspelled name"""

        available_keys = getattr(self, namespace).keys()
        matches = get_close_matches(name, available_keys, n=1, cutoff=0.6)
        return matches[0] if matches else None


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
    ) -> Callable[[str], Expression | None]: ...
    def get(self, namespace: namespace_names) -> Callable[[str], T | Expression | None]:
        def _get(name: str) -> T | Expression | None:
            return self.glob(namespace)[self(namespace)[name]]

        return _get

    def set(self, namespace: namespace_names):
        def _set(name: str, value: Any, address: Optional[str] = None):
            if address is None:
                if self.level > 0:
                    address = f"{name}-{uuid.uuid4()}"
                else:
                    address = name
            self.glob.write(namespace, address, value)
            self(namespace)[name] = address
            return address

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
