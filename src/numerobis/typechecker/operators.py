"""Operator type signatures and binary operation type checking rules."""

from ..nodes.unit import One
from .types import (
    AnyType,
    BoolType,
    FunctionType,
    IntType,
    ListType,
    MethodStruct,
    NoneType,
    NumberType,
    NumType,
    Overload,
    SliceType,
    StrType,
    VarType,
)

_numberoverload = Overload(
    FunctionType(params=[IntType(), IntType()], return_type=IntType()),
    FunctionType(params=[IntType(), NumType()], return_type=NumType()),
    FunctionType(params=[NumType(), NumType()], return_type=NumType()),
    FunctionType(params=[NumType(), IntType()], return_type=NumType()),
)
_boolnumberoverload = Overload(
    FunctionType(params=[IntType(), IntType()], return_type=BoolType()),
    FunctionType(params=[IntType(), NumType()], return_type=BoolType()),
    FunctionType(params=[NumType(), NumType()], return_type=BoolType()),
    FunctionType(params=[NumType(), IntType()], return_type=BoolType()),
)


def _conv(this, *types):
    return {
        f"__{typ.lower()}__": FunctionType(
            params=[AnyType(this)], return_type=AnyType(typ)
        )
        for typ in types
    }


_ops = ["add", "sub", "mul", "div", "mod", "pow"]
_boolops = ["lt", "gt", "le", "ge"]
_eq = {
    f"__{typ}__": FunctionType(params=[AnyType(), AnyType()], return_type=BoolType())
    for typ in ["eq", "ne"]
}

typetable: dict[str, MethodStruct] = {
    "Any": MethodStruct({}),
    "Var": MethodStruct({}),
    "Int": MethodStruct(
        {
            **_conv("Int", "Bool", "Str", "Num"),
            **{f"__{op}__": _numberoverload for op in _ops},
            **{f"__{op}__": _boolnumberoverload for op in _boolops},
            **_eq,
        }
    ),
    "Num": MethodStruct(
        {
            **_conv("Num", "Bool", "Str", "Int"),
            **{f"__{op}__": _numberoverload for op in _ops},
            **{f"__{op}__": _boolnumberoverload for op in _boolops},
            **_eq,
        }
    ),
    "Bool": MethodStruct({**_conv("Bool", "Bool", "Str", "Int", "Num"), **_eq}),
    "Str": MethodStruct(
        {
            **_conv("Str", "Bool", "Int", "Num"),
            "__add__": FunctionType(
                params=[StrType(), StrType()], return_type=StrType()
            ),
            "__mul__": FunctionType(
                params=[StrType(), NumberType(typ="Int", dim=One())],
                return_type=StrType(),
            ),
            "__getitem__": Overload(
                FunctionType(
                    params=[StrType(), IntType()],
                    return_type=StrType(),
                ),
                FunctionType(
                    params=[StrType(), SliceType()],
                    return_type=StrType(),
                ),
            ),
            "__setitem__": FunctionType(
                params=[StrType(), IntType(), StrType()],
                return_type=NoneType(),
            ),
            **{
                f"__{op}__": FunctionType(
                    params=[StrType(), StrType()], return_type=BoolType()
                )
                for op in _boolops
            },
            **_eq,
        },
    ),
    "List": MethodStruct(
        {
            **_conv("List", "Bool", "Str"),
            "__add__": FunctionType(
                params=[ListType(content=VarType("T")), ListType(content=VarType("T"))],
                return_type=ListType(content=VarType("T")),
            ),
            "__mul__": FunctionType(
                params=[
                    ListType(content=VarType("T")),
                    NumberType(typ="Int", dim=One()),
                ],
                return_type=ListType(content=VarType("T")),
            ),
            "__getitem__": Overload(
                FunctionType(
                    params=[ListType(content=VarType("T")), IntType()],
                    return_type=VarType("T"),
                ),
                FunctionType(
                    params=[ListType(content=VarType("T")), SliceType()],
                    return_type=ListType(content=VarType("T")),
                ),
            ),
            "__setitem__": FunctionType(
                params=[ListType(content=VarType("T")), IntType(), VarType("T")],
                return_type=NoneType(),
            ),
            **{
                f"__{op}__": FunctionType(
                    params=[ListType(), ListType()], return_type=BoolType()
                )
                for op in _boolops
            },
            **_eq,
        },
    ),
    "Range": MethodStruct({**_eq}),
    "Function": MethodStruct({**_eq}),
    "Dimension": MethodStruct({}),
    "None": MethodStruct({**_eq}),
}
