from astnodes import AstNode, Identifier
from classes import E
from typechecker.types import FunctionType, Overload, T, unify


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


def repr_dimension(
    dimension: list[AstNode | E], env: dict
) -> tuple[list[AstNode | E] | int]:
    """Find higher level representations of a base dimension combination"""
    reprs = []
    for name, value in env.items():
        if value.dimension == dimension:
            if len(reprs) < 3:
                reprs.append([Identifier(name=name)])
            elif len(reprs) == 3:
                reprs.append(1)
            else:
                reprs[-1] += 1

    return tuple(reprs) or (dimension,)


def _check_method(method, *args) -> FunctionType | None:
    if isinstance(method, FunctionType):
        return method.check_args(*args)
    elif isinstance(method, Overload):
        return next(
            (
                checked
                for func in method.functions
                if (checked := func.check_args(*args))
            ),
            None,
        )
    raise ValueError()


def _mismatch(a: T, b: T) -> tuple[str, str, str] | None:
    if not unify(a, b):
        return ("type", f"'{a.type()}'", f"'{b.type()}'")
    elif a.dim() != b.dim() and not (a.name("Never", "Any") or b.name("Never", "Any")):
        value = (
            "dimension",
            *(f"[[bold]{format_dimension(x.dim())}[/bold]]" for x in [a, b]),
        )
        return value  # type: ignore
