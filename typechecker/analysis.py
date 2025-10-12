from __future__ import annotations

from typing import Literal

from astnodes import (
    AstNode,
    BinOp,
    Float,
    Identifier,
    Integer,
    Operator,
    Scalar,
    Unit,
)
from classes import E, Env, ModuleMeta
from exceptions import Exceptions, uNameError


def analyze(module: ModuleMeta):
    def _analyze(typ: Literal["unit", "dimension"]):
        class analysis:
            def __init__(self, node: Unit, env: Env):
                self.typ: Literal["unit", "dimension"] = typ
                self.typs: Literal["units", "dimensions"] = typ + "s"
                self.errors = Exceptions(module=module)
                self.env: Env = env
                self.node: Unit = node

            def run(self) -> list:
                value = self.node.unit

                normalized = self.flatten(self.normalize(value))

                dimension = simplify(normalized)

                return dimension

            def normalize(self, nodes: list[AstNode]) -> list[AstNode | E]:
                """Normalize divisions to multiplications by inverse and filter trivial scalars"""
                res = []
                e = 1

                for node in nodes:
                    match node:
                        case Operator():
                            e = 1 if node.name == "mul" else -1
                        case Scalar() | Integer() | Float() if self._is_trivial_scalar(
                            node
                        ):
                            continue
                        case Scalar():
                            res.append(node if e == 1 else E(base=node, exponent=e))
                        case Identifier():
                            res.append(node if e == 1 else E(base=node, exponent=e))
                        case BinOp():
                            # only possible BinOp is 'pow'
                            base = self.normalize([node.left])[0]
                            exponent = self._extract_numeric_value(node.right)  # type: ignore
                            res.append(E(base=base, exponent=exponent * e))
                        case Unit():
                            u = self.normalize(node.unit)
                            if e == -1:
                                u = [
                                    E(
                                        base=item.base if isinstance(item, E) else item,
                                        exponent=(
                                            item.exponent if isinstance(item, E) else 1
                                        )
                                        * -1,
                                    )
                                    for item in u
                                ]
                            res.extend(u)

                return res

            def _is_trivial_scalar(self, node: Scalar | Integer | Float) -> bool:
                """Check if a scalar is trivial and should be filtered out"""
                value = getattr(node, "value", "")
                exponent = getattr(node, "exponent", "")
                return (value in {"1", "1.0"} and not exponent) or exponent == "0"

            def _extract_numeric_value(self, node: Scalar | Integer | Float) -> float:
                """Extract numeric value from Integer/Float node"""
                value = float(node.value)
                if hasattr(node, "exponent") and node.exponent:
                    value *= 10 ** float(node.exponent)
                return value

            def flatten(self, nodes: list):
                """Resolve references to base units/dimensions"""
                res = []

                for node in nodes:
                    match node:
                        case Identifier():
                            if node.name not in self.env(self.typs):
                                suggestion = self.env.suggest(self.typs)(node.name)

                                self.errors.throw(
                                    uNameError,
                                    f"undefined {self.typ} '{node.name}'",
                                    help=f"did you mean '{suggestion}'?"
                                    if suggestion
                                    else None,
                                    loc=node.loc,
                                )

                            resolved = self.env.get(self.typs)(node.name)
                            res.extend(resolved.dimension or [node])

                        case E():
                            base_nodes = (
                                node.base
                                if isinstance(node.base, list)
                                else [node.base]
                            )
                            flattened_base = self.flatten(base_nodes)
                            for item in flattened_base:
                                res.append(
                                    E(
                                        base=item.base if isinstance(item, E) else item,
                                        exponent=(
                                            item.exponent if isinstance(item, E) else 1
                                        )
                                        * node.exponent,
                                    )
                                )
                        case list():
                            res.extend(self.flatten(node))

                return res

        return lambda node, env: analysis(node=node, env=env).run()

    return _analyze


def simplify(nodes: list):
    """Combine like terms by summing exponents"""
    groups = {}

    for node in nodes:
        if isinstance(node, (E, Identifier)):
            base = node.base if isinstance(node, E) else node
            key = (type(base).__name__, getattr(base, "name", str(base)))
            exp = getattr(node, "exponent", 1)

            if key not in groups:
                groups[key] = {"base": base, "exponent": 0.0}
            groups[key]["exponent"] += exp

    return [
        E(base=g["base"], exponent=g["exponent"]) if g["exponent"] != 1 else g["base"]
        for g in groups.values()
        if g["exponent"] != 0
    ]


def format_dimension(dims) -> str:
    """Format dimension for error messages"""
    num, denom = [], []

    for d in dims:
        exp = 1
        name = None
        if isinstance(d, E):
            if isinstance(d.base, list):
                name = format_dimension(d.base)
                name = f"({name})" if len(d.base) > 1 else name
            exp = d.exponent
            d = d.base

        name = getattr(d, "name", getattr(d, "value", str(d))) if name is None else name

        target = num if float(getattr(d, "exponent", 1) or 1) > 0 else denom
        target.append(
            name if exp == 1 else f"{name}^{int(exp) if exp == int(exp) else exp}"
        )

    num_str = " * ".join(num) or "1"
    if not denom:
        return num_str

    denom_str = denom[0] if len(denom) == 1 else f"({' * '.join(denom)})"
    return f"{num_str} / {denom_str}"
