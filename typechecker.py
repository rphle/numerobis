import dataclasses
from typing import Literal

import rich

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


class Typechecker:
    def __init__(self, ast: list[AstNode], module: ModuleMeta):
        self.ast = ast
        self.module = module
        self.errors = Exceptions(module=module)

        self.dimensions = {}
        self.units = {}

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
        res = []

        for node in nodes:
            match node:
                case Scalar():
                    res.append(node)
                case Identifier():
                    if node.name not in getattr(self, typ):
                        self.errors.throw(
                            uNameError,
                            f"undefined {typ[:-1]} '{node.name}'",
                            loc=node.loc,
                        )
                    dim = self.flatten(getattr(self, typ)[node.name]["normalized"], typ)
                    res.extend(dim or [node])
                case E():
                    base = self.flatten(
                        list(node.base) if isinstance(node.base, list) else [node.base],
                        typ,
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
                    res.extend(self.flatten(node, typ))
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
                    if node.name not in self.units:
                        self.errors.throw(
                            uNameError, f"undefined unit '{node.name}'", loc=node.loc
                        )
                    res.extend(self.units[node.name]["dimension"])
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
            exp = getattr(d, "exponent", 1)

            target = num if exp > 0 else denom
            exp = abs(exp)
            target.append(name if exp == 1 else f"{name}^{exp}")

        num_str = " * ".join(num) or "1"
        return (
            f"{num_str} / {denom[0] if len(denom) == 1 else '(' + '·'.join(denom) + ')'}"
            if denom
            else num_str
        )

    def dimension_def(self, node):
        normalized = []
        if node.value:
            normalized = self.flatten(self.normalize(node.value.unit), typ="dimension")
        self.dimensions[node.name.name] = {"name": node.name, "normalized": normalized}

    def unit_def(self, node):
        normalized = []
        dimension: list[Scalar | Identifier | E | list] = []

        if node.dimension and not node.value:
            if node.dimension.name not in self.dimensions:
                self.errors.throw(
                    uNameError,
                    f"undefined dimension '{node.dimension.name}'",
                    loc=node.dimension.loc,
                )
            dimension = [node.dimension]
        elif node.value:
            normalized = self.flatten(self.normalize(node.value.unit), typ="unit")
            dimension = self.simplify(self.dimensionize(normalized))

            if node.dimension:
                expected = self.simplify(
                    self.dimensions[node.dimension.name]["normalized"]
                )
                if expected != dimension:
                    self.errors.throw(
                        Dimension_Mismatch,
                        f"unit '{node.name.name}' is not of dimension '{node.dimension.name}'",
                    )

        self.units[node.name.name] = {
            "name": node.name,
            "value": getattr(node.value, "unit", None),
            "normalized": normalized,
            "dimension": dimension,
        }

    def bin_op(self, node: BinOp):
        rich.print(node)
        sides = [{"unit": [], "dim": []} for _ in range(2)]

        for i, side in enumerate((node.left, node.right)):
            if isinstance(side, (Integer, Float)):
                sides[i]["unit"] = self.normalize(getattr(side.unit, "unit", []))
                sides[i]["dim"] = self.simplify(
                    self.dimensionize(self.flatten(sides[i]["unit"], "unit"))
                )

        if sides[0]["dim"] != sides[1]["dim"]:
            texts = [self.format_dimension(side["dim"]) for side in sides]
            self.errors.binOpMismatch(node, texts)

        print("Left dimension:", sides[0]["dim"])
        print("Right dimension:", sides[1]["dim"])

    def start(self):
        for node in self.ast:
            match node:
                case DimensionDefinition():
                    self.dimension_def(node)
                case UnitDefinition():
                    self.unit_def(node)
                case BinOp():
                    self.bin_op(node)
