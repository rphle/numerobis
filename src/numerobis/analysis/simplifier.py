from collections import defaultdict
from dataclasses import replace
from decimal import Decimal
from typing import Type

from ..classes import ModuleMeta
from ..exceptions.exceptions import Exceptions
from ..nodes.unit import (
    Call,
    Expression,
    Neg,
    One,
    Power,
    Product,
    Scalar,
    Sum,
    UnitNode,
)
from ..utils import camel2snake_pattern


def cancel(node: UnitNode | One) -> UnitNode | One:
    """Remove neutral/empty subnodes; return One() if fully canceled."""
    canceled = cancel_(node)
    return canceled if canceled is not None else One()


def cancel_(node: UnitNode | One) -> UnitNode | None:
    """Recursively strip neutral elements; return None if node vanishes."""
    match node:
        case Expression():
            return Expression(v) if (v := cancel(node.value)) else None
        case Product() | Sum():
            values = [v for val in node.values if (v := cancel(val))]
            if not values:
                return None
            if len(values) == 1:
                return values[0]
            return replace(node, values=values)
        case Neg() | Power() as n:
            attr = "value" if isinstance(n, Neg) else "base"
            val = cancel(getattr(n, attr))
            return replace(n, **{attr: val}) if val else None
        case Scalar():
            return None if not node.unit else cancel(node.unit.value)
    return node


class Simplifier:
    def __init__(self, module: ModuleMeta):
        """Initialize simplifier with module-bound error handler."""
        self.errors = Exceptions(module)

    def simplify(self, node: UnitNode, do_cancel: bool = True) -> Expression | One:
        """Fully simplify a node and optionally cancel neutral elements."""
        res = self._simplify(node)
        if do_cancel:
            res = cancel(res)
        return res if isinstance(res, (Expression, One)) else Expression(value=res)

    def _simplify(self, node: UnitNode):
        """Dispatch to type-specific simplify handler if available."""
        method_name = f"{camel2snake_pattern.sub('_', type(node).__name__).lower()}_"
        handler = getattr(self, method_name, None)

        if handler:
            return handler(node)
        return node

    def _flatten(self, values: list[UnitNode], op_type: Type[Product | Sum]):
        """Flatten nested operations of the same type and simplify children."""
        flat = []
        for val in values:
            s_val = self._simplify(val)
            if isinstance(s_val, op_type):
                flat.extend(s_val.values)
            elif not isinstance(s_val, One):
                flat.append(s_val)
        return flat

    def _finalize(
        self, values: list[UnitNode], op_type: Type[Product | Sum], identity: Decimal
    ):
        """Rebuild operation or return identity/single element if trivial."""
        if not values:
            return Scalar(identity)
        if len(values) == 1:
            return values[0]
        return op_type(values)

    def _decompose(self, node: UnitNode) -> tuple[Decimal, UnitNode]:
        """Extracts coefficient and base from a term (e.g., 2*x -> 2.0, x)."""
        if isinstance(node, Product):
            scalars = [v for v in node.values if isinstance(v, Scalar)]
            others = [v for v in node.values if not isinstance(v, Scalar)]

            if scalars:
                coeff = Decimal(1)
                for s in scalars:
                    coeff *= s.value

                if not others:
                    return coeff, One()

                base = others[0] if len(others) == 1 else Product(others)
                return coeff, base

        return Decimal(1), node

    def call_(self, node: Call):
        """Simplify call arguments."""
        return replace(
            node, args=[replace(a, value=self._simplify(a.value)) for a in node.args]
        )

    def expression_(self, node: Expression):
        """Simplify wrapped expression."""
        return self._simplify(node.value)

    def neg_(self, node: Neg):
        """Simplify negation and fold scalar/identity cases."""
        val = self._simplify(node.value)
        if isinstance(val, (One, Scalar)):
            v = Decimal(1) if isinstance(val, One) else val.value
            return Scalar(-v, loc=node.loc)
        return replace(node, value=val)

    def power_(self, node: Power):
        """Simplify exponentiation with constant folding and power rules."""
        base = self._simplify(node.base)
        exp = self._simplify(node.exponent)

        if isinstance(exp, Scalar):
            if exp.value == 0:
                return Scalar(Decimal(1))
            if exp.value == 1:
                return base

        match base:
            case One():
                return Scalar(Decimal(1))
            case Scalar() if isinstance(exp, Scalar):
                return Scalar(base.value**exp.value)
            case Power():  # (x^a)^b -> x^(a*b)
                new_exp = self._simplify(Product([base.exponent, exp]))
                return replace(base, exponent=new_exp)
            case Product():  # (a*b)^n -> a^n * b^n
                new_vals: list[UnitNode] = [
                    Power(base=v, exponent=exp, loc=base.loc.merge(exp.loc))
                    for v in base.values
                ]
                return self._simplify(Product(new_vals))

        return replace(node, base=base, exponent=exp)

    def product_(self, node: Product):
        """Simplify product: combine scalars and merge equal bases."""
        terms = self._flatten(node.values, Product)

        scalar_acc = Decimal(1)
        groups = defaultdict(list)  # Base -> List[Exponents]

        for term in terms:
            if isinstance(term, Scalar):
                scalar_acc *= term.value
            elif isinstance(term, Power):
                groups[term.base].append(term.exponent)
            else:
                groups[term].append(Scalar(Decimal(1)))

        new_values = []
        if scalar_acc != 1:
            new_values.append(Scalar(scalar_acc))

        for base, exps in groups.items():
            total_exp = self.sum_(Sum(exps)) if len(exps) > 1 else exps[0]

            # Check for x^1 or x^0
            if isinstance(total_exp, Scalar):
                if total_exp.value == 0:
                    continue
                if total_exp.value == 1:
                    new_values.append(base)
                    continue

            new_values.append(Power(base=base, exponent=total_exp, loc=base.loc))

        return self._finalize(new_values, Product, Decimal(1))

    def sum_(self, node: Sum):
        """Simplify sum: combine like terms and enforce dimension consistency."""
        terms = self._flatten(node.values, Sum)

        scalar_acc = Decimal(0)
        groups = defaultdict(Decimal)
        ref_base = None  # Track the single allowed dimension for this sum

        for term in terms:
            # Handle dimensionless scalars
            if isinstance(term, Scalar) and not getattr(term, "unit", None):
                scalar_acc += term.value
                continue

            coeff, base = self._decompose(term)

            if isinstance(base, One):
                scalar_acc += coeff
                continue

            # All non-scalar terms must share the same base dimension
            if ref_base is None:
                ref_base = base
            elif base != ref_base:
                self.errors.throw(543, loc=term.loc)

            groups[base] += coeff

        # Reconstruct
        new_values = []
        if scalar_acc != 0:
            new_values.append(Scalar(Decimal(scalar_acc)))

        for base, total_coeff in groups.items():
            if total_coeff == 0:
                continue
            if total_coeff == 1:
                new_values.append(base)
            else:
                # 3 * x -> Product([3, x])
                # If base is Product, prepend coefficient: 3 * (y*z) -> 3*y*z
                if isinstance(base, Product):
                    new_values.append(
                        Product([Scalar(Decimal(total_coeff)), *base.values])
                    )
                else:
                    new_values.append(Product([Scalar(Decimal(total_coeff)), base]))

        return self._finalize(new_values, Sum, Decimal(0))
