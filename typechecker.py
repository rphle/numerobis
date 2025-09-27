import dataclasses
from parser import Parser
from typing import Literal

import rich

from astnodes import (
    AstNode,
    BinOp,
    DimensionDefinition,
    Identifier,
    Operator,
    Scalar,
    Unit,
    UnitDefinition,
)
from exceptions import Exceptions, uDimensionError, uNameError
from lexer import lex


@dataclasses.dataclass(kw_only=True, frozen=True)
class E:
    base: Identifier | Scalar | list
    exponent: float


class Typechecker:
    def __init__(self, ast: list[AstNode], path: str | None = None):
        self.ast = ast
        self.path = path
        self.errors = Exceptions(path)

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
                case Scalar():
                    if not (
                        (node.value in {"1", "1.0"} and node.exponent == "")
                        or node.exponent == "0"
                    ):
                        res.append(node if e == 1 else E(base=node, exponent=e))
                case Identifier():
                    res.append(node if e == 1 else E(base=node, exponent=e))
                case BinOp():
                    # only possible BinOp is 'power'
                    base = self.normalize([node.left])[0]
                    exponent = {"Integer": int, "Float": float}[
                        type(node.right).__name__
                    ](
                        f"{node.right.value}{'e' if node.right.exponent else ''}{node.right.exponent}"  # type: ignore
                    )

                    res.append(
                        E(
                            base=base,
                            exponent=exponent * e,
                        )
                    )
                case Unit():
                    u = self.normalize(node.unit)
                    res.append(u if e == 1 else E(base=list(u), exponent=e))
                case _:
                    raise ValueError(f"Unknown node: {node}")

        return res

    def flatten(
        self,
        nodes: list[Scalar | Identifier | E | list],
        typ: Literal["dimension", "unit"],
    ):
        """
        Resolve everything to base units/dimensions
        """
        if not typ.endswith("s"):
            typ += "s"  # type: ignore

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
                    if len(base) == 1:
                        base = base[0]
                        if isinstance(base, E):
                            node = dataclasses.replace(
                                node,
                                exponent=node.exponent * base.exponent,
                                base=base.base,
                            )

                    res.append(node)
                case list():
                    res.extend(self.flatten(node, typ))
                case _:
                    raise ValueError(f"Unknown node: {node}")

        return res

    def dimensionize(
        self,
        nodes: list[Scalar | Identifier | E | list],
    ):
        """
        Resolve units to dimensions
        """
        res = []
        for node in nodes:
            match node:
                case Identifier():
                    if node.name not in self.units:
                        self.errors.throw(
                            uNameError,
                            f"undefined unit '{node.name}'",
                            loc=node.loc,
                        )
                    dim = self.units[node.name]["dimension"]
                    res.extend(dim)
                case E():
                    base = self.dimensionize(
                        list(node.base) if isinstance(node.base, tuple) else [node.base]
                    )
                    base = base[0] if len(base) == 1 else tuple(base)
                    res.append(dataclasses.replace(node, base=base))
                case _:
                    res.append(node)

        return res

    def dimension_def(self, node):
        normalized = []
        if node.value:
            normalized = self.flatten(self.normalize(node.value.unit), typ="dimension")

        self.dimensions[node.name.name] = {
            "name": node.name,
            "normalized": normalized,
        }

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
            dimension = self.dimensionize(normalized)

            if (
                node.dimension
                and self.dimensions[node.dimension.name]["normalized"] != dimension
            ):
                print(self.dimensions[node.dimension.name]["normalized"])
                print(dimension)
                self.errors.throw(
                    uDimensionError,
                    f"unit '{node.name.name}' is not of dimension '{node.dimension.name}'",
                )

        self.units[node.name.name] = {
            "name": node.name,
            "value": getattr(node.value, "unit", None),
            "normalized": normalized,
            "dimension": dimension,
        }

    def start(self):
        for node in ast:
            match node:
                case DimensionDefinition():
                    self.dimension_def(node)
                case UnitDefinition():
                    self.unit_def(node)


if __name__ == "__main__":
    path = "tests/test.und"
    source = open(path, "r").read()

    lexed = lex(source, debug=False)
    parser = Parser(lexed)
    ast = parser.start()

    tc = Typechecker(ast, path)
    tc.start()

    print()
    rich.print("DIMENSIONS:", tc.dimensions)
    print()
    rich.print("UNITS:", tc.units)
