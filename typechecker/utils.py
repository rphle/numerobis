from typing import Literal

from exceptions.exceptions import Mismatch

from .types import FunctionType, Overload, T, dimcheck, unify


class UnresolvedAnyParam(Exception):
    pass


def _check_method(method, *args) -> FunctionType | Mismatch | None:
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


def nomismatch(a: T, b: T) -> Mismatch | Literal[True]:
    if not (mismatch := unify(a, b)):
        return mismatch
    elif not (mismatch := dimcheck(a, b)):
        return mismatch
    return True
