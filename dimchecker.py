import dataclasses
from difflib import get_close_matches
from functools import lru_cache
from typing import Literal, Union

from astnodes import (
    AstNode,
    BinOp,
    DimensionDefinition,
    Float,
    FromImport,
    Identifier,
    Import,
    Integer,
    Operator,
    Scalar,
    Unit,
    UnitDefinition,
)
from classes import ModuleMeta
from exceptions import Dimension_Mismatch, Exceptions, uNameError


@dataclasses.dataclass(kw_only=True, frozen=True)
class E:
    base: Identifier | Scalar | list
    exponent: float


@dataclasses.dataclass(kw_only=True, frozen=True)
class NodeType:
    typ: str
    dimension: list
    unit: list | None = None
    dimensionless: bool = False


@dataclasses.dataclass(kw_only=True, frozen=True)
class Namespaces:
    names: dict[str, NodeType] = dataclasses.field(default_factory=dict)
    dimensions: dict[str, NodeType] = dataclasses.field(default_factory=dict)
    units: dict[str, NodeType] = dataclasses.field(default_factory=dict)


class Dimchecker:
    def __init__(
        self,
        ast: list[AstNode],
        module: ModuleMeta,
        namespaces: Namespaces | None = None,
    ):
        self.ast = ast
        self.module = module
        self.errors = Exceptions(module=module)
        self.ns = namespaces or Namespaces()

    @lru_cache(maxsize=128)
    def _get_suggestion(self, name: str, available_keys: tuple) -> str | None:
        """Get suggestion for misspelled name"""
        matches = get_close_matches(name, available_keys, n=1, cutoff=0.6)
        return matches[0] if matches else None

    def normalize(self, nodes: list[AstNode]) -> list[Union[AstNode, E]]:
        """Normalize divisions to multiplications by inverse and filter trivial scalars"""
        res = []
        e = 1

        for node in nodes:
            match node:
                case Operator():
                    e = 1 if node.name == "times" else -1
                case Scalar() | Integer() | Float() if self._is_trivial_scalar(node):
                    continue
                case Scalar():
                    res.append(node if e == 1 else E(base=node, exponent=e))
                case Identifier():
                    res.append(node if e == 1 else E(base=node, exponent=e))
                case BinOp():
                    # only possible BinOp is 'power'
                    base = self.normalize([node.left])[0]
                    exponent = self._extract_numeric_value(node.right)  # type: ignore
                    res.append(E(base=base, exponent=exponent * e))
                case Unit():
                    u = self.normalize(node.unit)
                    if e == -1:
                        u = [
                            E(
                                base=item.base if isinstance(item, E) else item,
                                exponent=(item.exponent if isinstance(item, E) else 1)
                                * -1,
                            )
                            for item in u
                        ]
                    res.extend(u)

        return res

    def _is_trivial_scalar(self, node: Union[Scalar, Integer, Float]) -> bool:
        """Check if a scalar is trivial and should be filtered out"""
        value = getattr(node, "value", "")
        exponent = getattr(node, "exponent", "")
        return (value in {"1", "1.0"} and not exponent) or exponent == "0"

    def _extract_numeric_value(self, node: Union[Integer, Float]) -> float:
        """Extract numeric value from Integer/Float node"""
        value = float(node.value)
        if hasattr(node, "exponent") and node.exponent:
            value *= 10 ** float(node.exponent)
        return value

    def flatten(
        self,
        nodes: list[Scalar | Identifier | E | list],
        typ: Literal["dimension", "unit"],
    ):
        """Resolve references to base units/dimensions"""
        ns = getattr(self.ns, f"{typ}s")
        res = []

        for node in nodes:
            match node:
                case Scalar():
                    res.append(node)
                case Identifier():
                    if node.name not in ns:
                        suggestion = self._get_suggestion(node.name, tuple(ns.keys()))
                        self.errors.throw(
                            uNameError,
                            f"undefined {typ} '{node.name}'",
                            help=f"did you mean '{suggestion}'?"
                            if suggestion
                            else None,
                            loc=node.loc,
                        )

                    resolved = self.flatten(getattr(ns[node.name], typ), typ=typ)
                    res.extend(resolved or [node])

                case E():
                    base_nodes = (
                        node.base if isinstance(node.base, list) else [node.base]
                    )
                    flattened_base = self.flatten(base_nodes, typ=typ)
                    for item in flattened_base:
                        res.append(
                            E(
                                base=item.base if isinstance(item, E) else item,
                                exponent=(item.exponent if isinstance(item, E) else 1)
                                * node.exponent,
                            )
                        )
                case list():
                    res.extend(self.flatten(node, typ=typ))
                case _:
                    raise ValueError(f"Unknown node: {node}")

        return res

    def simplify(self, nodes: list[Scalar | Identifier | E]):
        """Combine like terms by summing exponents"""
        groups = {}

        for node in nodes:
            if isinstance(node, (E, Identifier)):
                base = node.base if isinstance(node, E) else node
                key = (type(base).__name__, getattr(base, "name", str(base)))
                exp = getattr(node, "exponent", 1)

                if key not in groups:
                    groups[key] = {"base": base, "exponent": 0}
                groups[key]["exponent"] += exp

        return [
            E(base=g["base"], exponent=g["exponent"])
            if g["exponent"] != 1
            else g["base"]
            for g in groups.values()
            if g["exponent"] != 0
        ]

    def dimensionize(self, nodes: list[Scalar | Identifier | E | list]):
        """Convert units to their dimensions, filtering out all scalar expressions"""
        res = []

        for node in nodes:
            match node:
                case Identifier():
                    if node.name not in self.ns.units:
                        suggestion = self._get_suggestion(
                            node.name, tuple(self.ns.units.keys())
                        )
                        self.errors.throw(
                            uNameError,
                            f"undefined unit '{node.name}'",
                            help=f"did you mean '{suggestion}'?"
                            if suggestion
                            else None,
                            loc=node.loc,
                        )
                    res.extend(self.ns.units[node.name].dimension)

                case E():
                    if isinstance(node.base, (Scalar, Integer, Float)):
                        continue

                    base = [node.base] if not isinstance(node.base, list) else node.base
                    base = self.dimensionize(base)
                    for item in base:
                        res.append(
                            E(
                                base=item.base if isinstance(item, E) else item,
                                exponent=(item.exponent if isinstance(item, E) else 1)
                                * node.exponent,
                            )
                        )
                case _:
                    res.append(node)

        return res

    def format_dimension(self, dims) -> str:
        """Format dimension for error messages"""
        num, denom = [], []

        for d in dims:
            if hasattr(d, "base"):
                name = getattr(d.base, "name", getattr(d.base, "value", str(d.base)))
            else:
                name = getattr(d, "name", getattr(d, "value", str(d)))

            exp = abs(getattr(d, "exponent", 1))
            target = num if getattr(d, "exponent", 1) > 0 else denom
            target.append(
                name if exp == 1 else f"{name}^{int(exp) if exp == int(exp) else exp}"
            )

        num_str = " * ".join(num) or "1"
        if not denom:
            return num_str

        denom_str = denom[0] if len(denom) == 1 else f"({' * '.join(denom)})"
        return f"{num_str} / {denom_str}"

    def _filter_dimensionless_identifiers(self, dimension_list: list) -> list:
        def is_dimensionless(item):
            if isinstance(item, Identifier):
                return (
                    item.name in self.ns.dimensions
                    and self.ns.dimensions[item.name].dimensionless
                )
            if hasattr(item, "base") and isinstance(item.base, Identifier):
                return (
                    item.base.name in self.ns.dimensions
                    and self.ns.dimensions[item.base.name].dimensionless
                )
            return False

        return [item for item in dimension_list if not is_dimensionless(item)]

    def dimension_def(self, node: DimensionDefinition):
        """Process dimension definitions"""
        normalized = []
        is_dimensionless = False

        if node.value:
            normalized = self.flatten(self.normalize(node.value.unit), typ="dimension")
            normalized = self.simplify(normalized)
            is_dimensionless = len(normalized) == 0

        self.ns.dimensions[node.name.name] = NodeType(
            typ="dimension",
            dimension=normalized,
            dimensionless=is_dimensionless,
        )

    def unit_def(self, node: UnitDefinition):
        """Process unit definitions with proper dimension checking"""
        normalized = []
        dimension = []

        if node.dimension and not node.value:
            dimension = [node.dimension]
        elif node.value:
            normalized = self.flatten(self.normalize(node.value.unit), typ="unit")
            dimension = self.simplify(self.dimensionize(normalized))

            if node.dimension:
                if node.dimension.name not in self.ns.dimensions:
                    suggestion = self._get_suggestion(
                        node.dimension.name, tuple(self.ns.dimensions.keys())
                    )
                    self.errors.throw(
                        uNameError,
                        f"undefined dimension '{node.dimension.name}'",
                        help=f"did you mean '{suggestion}'?" if suggestion else None,
                        loc=node.dimension.loc,
                    )

                dim_info = self.ns.dimensions[node.dimension.name]
                expected_dim = dim_info.dimension

                if dim_info.dimensionless:
                    expected = []
                elif not expected_dim:
                    expected = [Identifier(name=node.dimension.name)]
                else:
                    expected = self._filter_dimensionless_identifiers(expected_dim)

                if expected != dimension:
                    expected_str = self.format_dimension(expected)
                    actual_str = self.format_dimension(dimension)
                    self.errors.throw(
                        Dimension_Mismatch,
                        f"unit '{node.name.name}' declared as '{node.dimension.name}' [{expected_str}] but has dimension [{actual_str}]",
                        loc=node.name.loc,
                    )

        self.ns.units[node.name.name] = NodeType(
            typ="unit", dimension=dimension, unit=normalized
        )

    def bin_op(self, node: BinOp):
        """Check dimensional consistency in addition and subtraction operations"""
        if node.op.name not in {"plus", "minus"}:
            return

        sides = []
        for side in (node.left, node.right):
            if isinstance(side, (Integer, Float)) and hasattr(side, "unit"):
                unit_expr = self.normalize(getattr(side.unit, "unit", []))
                dimension = self.simplify(
                    self.dimensionize(self.flatten(unit_expr, typ="unit"))
                )
                sides.append(dimension)

        if len(sides) == 2 and sides[0] != sides[1]:
            dim_strs = [self.format_dimension(side) for side in sides]
            self.errors.binOpMismatch(node, dim_strs)

    def start(self):
        for node in self.ast:
            match node:
                case Import() | FromImport():
                    pass
                case DimensionDefinition():
                    self.dimension_def(node)
                case UnitDefinition():
                    self.unit_def(node)
                case BinOp():
                    self.bin_op(node)
