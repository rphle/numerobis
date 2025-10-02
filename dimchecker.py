import dataclasses
from difflib import get_close_matches
from typing import Literal

from astnodes import (
    AstNode,
    BinOp,
    DimensionDefinition,
    Float,
    Identifier,
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


@dataclasses.dataclass(kw_only=True, frozen=True)
class Namespaces:
    names: dict[str, NodeType] = dataclasses.field(default_factory=dict)
    dimensions: dict[str, NodeType] = dataclasses.field(default_factory=dict)
    units: dict[str, NodeType] = dataclasses.field(default_factory=dict)


class Dimchecker:
    def __init__(self, ast: list[AstNode], module: ModuleMeta):
        self.ast = ast
        self.module = module
        self.errors = Exceptions(module=module)

        self.ns = Namespaces()

    def _get_suggestion(self, name: str, available: dict) -> str | None:
        matches = get_close_matches(name, available.keys(), n=1, cutoff=0.6)
        return matches[0] if matches else None

    def normalize(self, nodes):
        """
        Modify parse AST and normalize divisions to multiplication by the inverse
        """
        res = []
        e = 1
        for node in nodes:
            match node:
                case Operator():
                    e = 1 if node.name == "times" else -1
                case Scalar() if not (
                    (node.value in {"1", "1.0"} and not node.exponent)
                    or node.exponent == "0"
                ):
                    res.append(node if e == 1 else E(base=node, exponent=e))
                case Identifier():
                    res.append(node if e == 1 else E(base=node, exponent=e))
                case BinOp():
                    # only possible BinOp is 'power'
                    base = self.normalize([node.left])[0]
                    exp_type = type(node.right).__name__
                    exponent = {"Integer": int, "Float": float}[exp_type](
                        f"{node.right.value}{'e' if node.right.exponent else ''}{node.right.exponent}"  # type: ignore
                    )
                    res.append(E(base=base, exponent=exponent * e))
                case Unit():
                    u = self.normalize(node.unit)
                    if e == -1:
                        res.extend(
                            [
                                E(
                                    base=item.base if isinstance(item, E) else item,
                                    exponent=(
                                        item.exponent if isinstance(item, E) else 1
                                    )
                                    * e,
                                )
                                for item in u
                            ]
                        )
                    else:
                        res.extend(u)
        return res

    def flatten(
        self,
        nodes: list[Scalar | Identifier | E | list],
        typ: Literal["dimension", "unit"],
    ):
        """
        Resolve everything to base units/dimensions
        """
        typ = typ if typ.endswith("s") else f"{typ}s"  # type: ignore
        ns = getattr(self.ns, typ)
        res = []

        for node in nodes:
            match node:
                case Scalar():
                    res.append(node)
                case Identifier():
                    if node.name not in ns:
                        suggestion = self._get_suggestion(node.name, ns)
                        self.errors.throw(
                            uNameError,
                            f"undefined {typ[:-1]} '{node.name}'",
                            help=f"did you mean '{suggestion}'?"
                            if suggestion
                            else None,
                            loc=node.loc,
                        )
                    dim = self.flatten(
                        getattr(ns[node.name], typ.removesuffix("s")), typ=typ
                    )
                    res.extend(dim or [node])
                case E():
                    base = self.flatten(
                        list(node.base) if isinstance(node.base, list) else [node.base],
                        typ=typ,
                    )
                    for item in base:
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
                key = (
                    type(base).__name__,
                    base.name if isinstance(base, Identifier) else str(base),
                )
                exp = node.exponent if isinstance(node, E) else 1
                groups.setdefault(key, {"base": base, "exponent": 0})
                groups[key]["exponent"] += exp

        return [
            E(base=g["base"], exponent=g["exponent"])
            if g["exponent"] != 1
            else g["base"]
            for g in groups.values()
            if g["exponent"] != 0
        ]

    def dimensionize(self, nodes: list[Scalar | Identifier | E | list]):
        """Resolve units to dimensions"""
        res = []
        for node in nodes:
            match node:
                case Identifier():
                    if node.name not in self.ns.units:
                        suggestion = self._get_suggestion(node.name, self.ns.units)
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
                    base = self.dimensionize(
                        list(node.base) if isinstance(node.base, list) else [node.base]
                    )
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
        num, denom = [], []

        for d in dims:
            name = d.base.name if hasattr(d, "base") else d.name
            exp = abs(getattr(d, "exponent", 1))
            target = num if getattr(d, "exponent", 1) > 0 else denom
            target.append(
                name if exp == 1 else f"{name}^{int(exp) if exp == int(exp) else exp}"
            )

        num_str = " * ".join(num) or "1"
        if not denom:
            return num_str
        return (
            f"{num_str} / {denom[0]}"
            if len(denom) == 1
            else f"{num_str} / ({' * '.join(denom)})"
        )

    def dimension_def(self, node):
        normalized = []
        if node.value:
            normalized = self.flatten(self.normalize(node.value.unit), typ="dimension")
            normalized = self.simplify(normalized)
        self.ns.dimensions[node.name.name] = NodeType(
            typ="dimension",
            dimension=normalized,
        )

    def unit_def(self, node):
        normalized = []
        dimension: list[Scalar | Identifier | E | list] = []

        if node.dimension and not node.value:
            if node.dimension.name not in self.ns.dimensions:
                suggestion = self._get_suggestion(
                    node.dimension.name, self.ns.dimensions
                )
                self.errors.throw(
                    uNameError,
                    f"undefined dimension '{node.dimension.name}'",
                    help=f"did you mean '{suggestion}'?" if suggestion else None,
                    loc=node.dimension.loc,
                )
            dimension = [node.dimension]
        elif node.value:
            normalized = self.flatten(self.normalize(node.value.unit), typ="unit")
            dimension = self.simplify(self.dimensionize(normalized))

            if node.dimension:
                if node.dimension.name not in self.ns.dimensions:
                    suggestion = self._get_suggestion(
                        node.dimension.name, self.ns.dimensions
                    )
                    self.errors.throw(
                        uNameError,
                        f"undefined dimension '{node.dimension.name}'",
                        help=f"did you mean '{suggestion}'?" if suggestion else None,
                        loc=node.dimension.loc,
                    )

                expected = self.ns.dimensions[node.dimension.name].dimension

                if expected != dimension:
                    expected_str, actual_str = (
                        self.format_dimension(expected),
                        self.format_dimension(dimension),
                    )
                    self.errors.throw(
                        Dimension_Mismatch,
                        f"unit '{node.name.name}' declared as '{node.dimension.name}' [{expected_str}] but has dimension [{actual_str}]",
                        loc=node.name.loc,
                    )

        self.ns.units[node.name.name] = NodeType(
            typ="unit", dimension=dimension, unit=normalized
        )

    def bin_op(self, node: BinOp):
        if node.op.name not in {"plus", "minus"}:
            return
        sides = [{"unit": [], "dim": []} for _ in range(2)]

        for i, side in enumerate((node.left, node.right)):
            if isinstance(side, (Integer, Float)):
                sides[i]["unit"] = self.normalize(getattr(side.unit, "unit", []))
                sides[i]["dim"] = self.simplify(
                    self.dimensionize(self.flatten(sides[i]["unit"], typ="unit"))
                )

        if sides[0]["dim"] != sides[1]["dim"]:
            texts = [self.format_dimension(side["dim"]) for side in sides]
            self.errors.binOpMismatch(node, texts)

    def start(self):
        for node in self.ast:
            match node:
                case DimensionDefinition():
                    self.dimension_def(node)
                case UnitDefinition():
                    self.unit_def(node)
                case BinOp():
                    self.bin_op(node)
