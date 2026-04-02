from ..exceptions.exceptions import Mismatch
from .types import FunctionType, Overload


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
