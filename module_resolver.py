from functools import lru_cache
from pathlib import Path
from typing import Optional


class ModuleResolver:
    def __init__(
        self,
        stdlib_path: Optional[str | Path] = None,
        search_paths: list[str | Path] = [],
    ):
        self.stdlib_path = (
            Path(stdlib_path) if stdlib_path else Path(__file__).parent / "stdlib"
        )
        self.search_paths = [Path(p) for p in search_paths]

    @lru_cache(maxsize=128)
    def resolve(self, name: str) -> Path:
        """Resolve a module name to a file path."""
        file = name.replace(".", "/") + ".und"

        # Check stdlib first
        if (path := self.stdlib_path / file).is_file():
            return path.resolve()

        # Check search paths
        for search_dir in set(self.search_paths):
            if (path := search_dir / file).is_file():
                return path.resolve()

        raise FileNotFoundError(f"Module '{name}' not found")
