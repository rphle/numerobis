from nodes.unit import One

from .types import (
    AnyType,
    BoolType,
    FloatType,
    FunctionType,
    IntType,
    ListType,
    NoneType,
    NumberType,
    Overload,
    SliceType,
    StrType,
    Struct,
    VarType,
)

_numberoverload = Overload(
    FunctionType(params=[IntType(), IntType()], return_type=IntType()),
    FunctionType(params=[IntType(), FloatType()], return_type=FloatType()),
    FunctionType(params=[FloatType(), FloatType()], return_type=FloatType()),
    FunctionType(params=[FloatType(), IntType()], return_type=FloatType()),
)
_boolnumberoverload = Overload(
    FunctionType(params=[IntType(), IntType()], return_type=BoolType()),
    FunctionType(params=[IntType(), FloatType()], return_type=BoolType()),
    FunctionType(params=[FloatType(), FloatType()], return_type=BoolType()),
    FunctionType(params=[FloatType(), IntType()], return_type=BoolType()),
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

typetable: dict[str, Struct] = {
    "Any": Struct({}),
    "Int": Struct(
        {
            **_conv("Int", "Bool", "Str", "Float"),
            **{f"__{op}__": _numberoverload for op in _ops},
            **{f"__{op}__": _boolnumberoverload for op in _boolops},
            **_eq,
        }
    ),
    "Float": Struct(
        {
            **_conv("Float", "Bool", "Str", "Int"),
            **{f"__{op}__": _numberoverload for op in _ops},
            **{f"__{op}__": _boolnumberoverload for op in _boolops},
            **_eq,
        }
    ),
    "Bool": Struct({**_conv("Bool", "Bool", "Str"), **_eq}),
    "Str": Struct(
        {
            **_conv("Str", "Bool"),
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
    "List": Struct(
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
    "Range": Struct({**_eq}),
    "Function": Struct({**_eq}),
    "Dimension": Struct({}),
    "None": Struct({**_eq}),
}
