from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from astnodes import AstNode, FromImport, Import
from classes import ModuleMeta
from dimchecker import Namespaces, NodeType
from exceptions import uCircularImport, uImportError, uModuleNotFound
from module import Module


@dataclass
class ModuleInfo:
    """Information about a loaded module"""

    module: "Module"
    path: Path
    namespaces: "Namespaces"
    exports: Dict[str, "NodeType"] = field(default_factory=dict)
    is_stdlib: bool = False


class ModuleResolver:
    """Resolves module names to file paths with caching"""

    def __init__(
        self,
        stdlib_path: Optional[str] = None,
        search_paths: Optional[List[str]] = None,
    ):
        self.stdlib_path = (
            Path(stdlib_path) if stdlib_path else Path(__file__).parent / "stdlib"
        )
        self.search_paths = [Path(p) for p in (search_paths or ["."])]

    @lru_cache(maxsize=128)
    def resolve(self, module_name: str, current_file: Optional[str] = None) -> tuple:
        """Resolve a module name to a file path. Returns (path, is_stdlib)"""
        module_file = module_name.replace(".", "/") + ".und"

        # Check stdlib first
        stdlib_path = self.stdlib_path / module_file
        if stdlib_path.is_file():
            return stdlib_path.resolve(), True

        # Check search paths
        current_dir = Path(current_file).parent if current_file else Path(".")
        for search_dir in [current_dir] + self.search_paths:
            candidate = search_dir / module_file
            if candidate.is_file():
                return candidate.resolve(), False

        raise FileNotFoundError(f"Module '{module_name}' not found")


class ModuleSystem:
    """Main interface for the module system with improved circular import detection"""

    def __init__(
        self,
        stdlib_path: Optional[str] = None,
        search_paths: Optional[List[str]] = None,
    ):
        self.resolver = ModuleResolver(stdlib_path, search_paths)
        self.loaded_modules: Dict[Path, ModuleInfo] = {}
        self.loading_stack: List[Path] = []

    def _check_circular_import(self, path: Path):
        """Check for circular imports and raise error if found"""
        if path in self.loading_stack:
            cycle_start = self.loading_stack.index(path)
            cycle_names = [p.stem for p in self.loading_stack[cycle_start:] + [path]]
            uCircularImport(
                f"Circular import detected: {' -> '.join(cycle_names)}",
                module=ModuleMeta(str(path), ""),
                help="Remove circular dependencies between these modules",
            )

    def load_module(
        self, module_name: str, current_file: Optional[str] = None
    ) -> ModuleInfo:
        """Load a module by name with proper circular import detection"""
        try:
            path, is_stdlib = self.resolver.resolve(module_name, current_file)
        except FileNotFoundError:
            uModuleNotFound(
                f"No module named '{module_name}'",
                module=ModuleMeta(current_file or "<unknown>", ""),
                help="Check the module name and ensure the file exists",
            )
            raise

        if path in self.loaded_modules and path not in self.loading_stack:
            return self.loaded_modules[path]

        self._check_circular_import(path)
        self.loading_stack.append(path)

        module = Module(str(path))
        module.parse()

        module_info = ModuleInfo(
            module=module, path=path, namespaces=Namespaces(), is_stdlib=is_stdlib
        )

        self._process_imports(module.ast, module_info)

        dimchecker = module.dimcheck(module_info.namespaces)
        module_info.namespaces = dimchecker.ns
        module_info.exports = self._create_exports(module_info)

        self.loaded_modules[path] = module_info
        self.loading_stack.pop()

        return module_info

    def load(self, path: str) -> ModuleInfo:
        """Load the main module (entry point)"""
        main_path = Path(path).resolve()
        module = Module(str(main_path))
        module.parse()

        module_info = ModuleInfo(
            module=module, path=main_path, namespaces=Namespaces(), is_stdlib=False
        )

        self._process_imports(module.ast, module_info)

        dimchecker = module.dimcheck(module_info.namespaces)
        module_info.namespaces = dimchecker.ns

        return module_info

    def _process_imports(self, ast: List[AstNode], current_module: ModuleInfo):
        """Process all import statements in an AST"""
        for node in ast:
            if isinstance(node, Import):
                self._handle_import(node, current_module)
            elif isinstance(node, FromImport):
                self._handle_from_import(node, current_module)

    def _handle_import(self, node: Import, current_module: ModuleInfo):
        """Handle 'import module_name [as alias]' statements"""
        imported_module = self.load_module(node.module.name, str(current_module.path))
        import_name = node.alias.name if node.alias else node.module.name
        self._merge_with_prefix(
            current_module.namespaces, imported_module.exports, import_name
        )

    def _handle_from_import(self, node: FromImport, current_module: ModuleInfo):
        """Handle 'from module_name import ...' statements"""
        imported_module = self.load_module(node.module.name, str(current_module.path))

        if node.names is None:  # from module import *
            self._merge_all(current_module.namespaces, imported_module.exports)
        else:
            for i, name in enumerate(node.names):
                if name.name not in imported_module.exports:
                    available = list(imported_module.exports.keys())[:5]
                    more_text = (
                        f" (and {len(imported_module.exports) - 5} more)"
                        if len(imported_module.exports) > 5
                        else ""
                    )
                    uImportError(
                        f"Cannot import name '{name.name}' from '{node.module.name}'",
                        module=ModuleMeta(str(current_module.path), ""),
                        help=f"Available names: {', '.join(available)}{more_text}",
                        loc=name.loc,
                    )

                local_name = (
                    node.aliases[i].name
                    if node.aliases and i < len(node.aliases) and node.aliases[i]
                    else name.name
                )
                self._add_to_namespace(
                    current_module.namespaces,
                    local_name,
                    imported_module.exports[name.name],
                )

    def _merge_with_prefix(
        self, target_ns: "Namespaces", exports: Dict[str, "NodeType"], prefix: str
    ):
        """Merge exports into target namespace with a prefix"""
        for name, node_type in exports.items():
            self._add_to_namespace(target_ns, f"{prefix}.{name}", node_type)

    def _merge_all(self, target_ns: "Namespaces", exports: Dict[str, "NodeType"]):
        """Merge all public exports into target namespace"""
        for name, node_type in exports.items():
            if not name.startswith("_"):
                self._add_to_namespace(target_ns, name, node_type)

    def _add_to_namespace(
        self, target_ns: "Namespaces", name: str, node_type: "NodeType"
    ):
        """Add a single item to the appropriate namespace"""
        namespace_map = {
            "dimension": target_ns.dimensions,
            "unit": target_ns.units,
        }
        target_namespace = namespace_map.get(node_type.typ, target_ns.names)
        target_namespace[name] = node_type

    def _create_exports(self, module_info: ModuleInfo) -> Dict[str, "NodeType"]:
        """Create the public interface for a module"""
        exports = {}
        for namespace in (
            module_info.namespaces.dimensions,
            module_info.namespaces.units,
            module_info.namespaces.names,
        ):
            exports.update(
                {
                    name: item
                    for name, item in namespace.items()
                    if not name.startswith("_")
                }
            )
        return exports
