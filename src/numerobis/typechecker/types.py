"""Type system definitions and type variable environment management."""

from dataclasses import dataclass, field, replace
from typing import Any, Callable, Literal, Optional, Union, overload

from ..exceptions.exceptions import Mismatch
from ..nodes.core import VarEnv
from ..nodes.unit import AnyDim, Expression, One
from ..utils import isanyofinstance

T = Union[
    "NoneType",
    "VarType",
    "NeverType",
    "AnyType",
    "RangeType",
    "NumberType",
    "BoolType",
    "StrType",
    "SliceType",
    "ListType",
    "FunctionType",
]


@dataclass(kw_only=True, frozen=True)
class UType:
    _meta: dict = field(default_factory=dict, hash=False)
    node: Optional[int] = None
    dim: Expression | One | AnyDim = AnyDim()

    @overload
    def name(self) -> str: ...
    @overload
    def name(self, *names: str) -> str: ...
    def name(self, *names: Optional[str]) -> str | bool:
        n = self.__class__.__name__.removesuffix("Type")
        if names:
            return n in names
        return n

    def edit(self, **kwargs):
        if "_meta" not in kwargs:
            kwargs["_meta"] = dict(self._meta)
        return replace(self, **kwargs)

    def complete(
        self,
        varenv: VarEnv,
        value: Optional[T] = None,
        fingerprint: Optional[int] = None,
    ):
        """Complete/fingerprint anonymous types ?T"""
        return self

    def meta(self, key, value=None):
        if value is not None:
            self._meta[key] = value
        return self._meta.get(key)

    def __str__(self):
        return f"'{self.name()}'"


class NoneType(UType):
    dim = One()

    def __eq__(self, other) -> bool:
        return isinstance(other, NoneType)


@dataclass(kw_only=True, frozen=True)
class NumberType(UType):
    typ: Literal["Int", "Num"] = "Num"
    dim: Expression | One | AnyDim = AnyDim()
    value: float | int = 0

    def __str__(self) -> str:
        if isinstance(self.dim, AnyDim):
            d = "[[bold]Any[/bold]]"
        else:
            d = str(self.dim) if self.dim else "[[bold]1[/bold]]"
        return f"'{self.typ}{d}'"

    @overload
    def name(self) -> str: ...
    @overload
    def name(self, *names: str) -> str: ...
    def name(self, *names: Optional[str]) -> str | bool:
        n = self.typ
        if names:
            return n in names
        return n

    def complete(
        self,
        varenv: VarEnv,
        value: Optional[T] = None,
        fingerprint: Optional[int] = None,
    ):
        return self.edit(
            dim=self.dim.complete(varenv, value.dim if value else None, fingerprint)
        )


@dataclass(kw_only=True, frozen=True)
class BoolType(UType):
    def __eq__(self, other) -> bool:
        return isinstance(other, BoolType)


@dataclass(kw_only=True, frozen=True)
class StrType(UType):
    def __eq__(self, other) -> bool:
        return isinstance(other, StrType)


@dataclass(frozen=True)
class VarType(UType):
    _name: str
    kind: str = "types"
    fingerprint: int = -1
    last_env: Optional[VarEnv] = field(default=None, compare=False, hash=False)

    def __str__(self) -> str:
        completion = ""
        if self.last_env is not None and self._name in self.last_env[self.kind]:
            completion = f"[{str(self.last_env[self.kind][self._name])}]"
            completion = completion.replace("'", "")
        return f"'?{self._name}{completion}'"

    def complete(
        self,
        varenv: VarEnv,
        value: Optional[T] = None,
        fingerprint: Optional[int] = None,
    ):
        if fingerprint is not None:
            object.__setattr__(self, "fingerprint", fingerprint)
        object.__setattr__(self, "last_env", varenv)

        if value is None:
            return varenv[self.kind].get(self._name, self)
        if self._name not in varenv[self.kind]:
            varenv[self.kind][self._name] = value
            return value

        unified = unify(value, varenv[self.kind][self._name])
        if isinstance(unified, Mismatch):
            return self

        varenv[self.kind][self._name] = unified
        return unified


@dataclass(kw_only=True, frozen=True)
class UndefinedType(UType):
    pass


@dataclass(kw_only=True, frozen=True)
class ListType(UType):
    content: T = field(default_factory=lambda: AnyType())
    dim: Expression | One | AnyDim = field(
        default_factory=lambda: AnyDim(), compare=False
    )

    def __post_init__(self):
        if self.dim is None:
            object.__setattr__(self, "dim", self.content.dim)

    def __str__(self) -> str:
        return f"'List[{str(self.content).strip("'")}]'"

    def complete(
        self,
        varenv: VarEnv,
        value: Optional[T] = None,
        fingerprint: Optional[int] = None,
    ):
        completed = self.content.complete(
            varenv, getattr(value, "content", None), fingerprint=fingerprint
        )
        return self.edit(content=completed, dim=completed.dim)


@dataclass(kw_only=True, frozen=True)
class SliceType(UType):
    def __eq__(self, other):
        return isinstance(other, SliceType)


@dataclass(kw_only=True, frozen=True)
class RangeType(UType):
    value: NumberType = NumberType(typ="Int", dim=One())

    def __str__(self):
        return f"'Range[{self.value}]'"

    def __eq__(self, other):
        if not isinstance(other, RangeType):
            return False
        return self.value == other.value


@dataclass(kw_only=True, frozen=True)
class FunctionType(UType):
    params: list[T] = field(default_factory=list)
    return_type: T = field(default_factory=lambda: AnyType())
    param_names: list[str] = field(default_factory=list)
    param_addrs: list[str] = field(default_factory=list)
    param_defaults: list[T] = field(default_factory=list)
    arity: tuple[int, int] = (0, 0)
    unresolved: Optional[Literal["recursive", "parameters"]] = None
    extern: bool = False
    _name: Optional[str] = field(default=None, compare=False)
    _self: Optional[T] = field(default=None)
    _loc: Any = field(default=None)

    def __str__(self):
        args = [
            f"{name}: {str(param).strip("'")}"
            for name, param in zip(self.param_names, self.params)
        ]
        if self.arity[0] != self.arity[1]:
            args.insert(self.arity[0], "/")

        dot = "·" if self._self else ""
        return dot + f"![\\[{', '.join(args)}], {str(self.return_type).strip('')}]"

    def check_args(self, *args: T) -> "FunctionType | Mismatch | None":
        varenv = VarEnv()
        params = [param.complete(varenv, arg) for param, arg in zip(self.params, args)]

        if len(args) != len(self.params):
            return
        for param, arg in zip(params, args):
            if not (mismatch := nomismatch(param, arg, unify=True)):
                return mismatch

        return self.edit(return_type=self.return_type.complete(varenv))


@dataclass(kw_only=True, frozen=True)
class Constant(UType):
    value: T


class AnyType(UType):
    unresolved: Optional[str] = None

    def __new__(cls, name: str = "any", unresolved=None, **kwargs) -> "T":
        if name.lower() == "any":
            return super().__new__(cls)

        t = {
            "none": NoneType(),
            "number": NumberType(),
            "int": NumberType(typ="Int"),
            "num": NumberType(typ="Num"),
            "bool": BoolType(),
            "str": StrType(),
            "list": ListType(),
            "slice": SliceType(),
            "range": RangeType(),
            "function": FunctionType(),
        }.get(name.strip().lower())

        if t is None:
            raise ValueError(f"Unknown type name: {name!r}")

        t = t.edit(**kwargs)
        return t

    def __init__(self, name="any", unresolved=None, **kwargs):
        self.unresolved = unresolved
        super().__init__()


class Overload:
    def __init__(self, *functions: "FunctionType|Overload"):
        self.functions: list[FunctionType] = []
        for func in functions:
            self.functions.extend(
                [func] if isinstance(func, FunctionType) else func.functions
            )


@dataclass(frozen=True)
class Struct:
    fields: dict[str, T | Overload]

    def __getitem__(self, key: str) -> T | Overload | None:
        return self.fields.get(key)


class IntType:
    def __new__(cls) -> NumberType:
        return NumberType(typ="Int")


class NumType:
    def __new__(cls) -> NumberType:
        return NumberType(typ="Num")


@dataclass(kw_only=True, frozen=True)
class NeverType(UType):
    dim: AnyDim = AnyDim()

    def __eq__(self, other) -> bool:
        return True

    def unify(self, other: UType) -> UType:
        object.__setattr__(self, "__class__", type(other))
        self.__init__(**other.__dict__)
        return self


# -------------------------------------------------- I CAN NOT RESOLVE THE CIRCULAR DEPENDENCY BETWEEN THESE TWO MODULES -----------------------------------------------------


def nomismatch(a: T, b: T, unify: bool = False) -> Mismatch | Literal[True]:
    tmode = unify_type if unify else match_type
    dmode = unify_dim if unify else match_dim

    if not (mismatch := tmode(a, b)):
        assert isinstance(mismatch, Mismatch)
        return mismatch

    elif not (mismatch := dmode(a, b)):
        assert isinstance(mismatch, Mismatch)
        return mismatch

    return True


def unify(a: T, b: T) -> T | Mismatch:
    value = unify_type(a, b)
    if isinstance(value, Mismatch):
        return value
    value = unify_dim(a, b)
    return value


def unify_never(a: T, b: T) -> T:
    if isinstance(a, NeverType):
        a.unify(b)
        return b
    elif isinstance(b, NeverType):
        b.unify(a)
        return a
    return a


# -------------------------


def _check_func(
    a: FunctionType, b: FunctionType, test: Callable, mismatch: Mismatch
) -> list | Mismatch:
    if a.arity != b.arity or bool(a._self) != bool(b._self):
        # since methods only appear bound, we don't need to check for the exact self type
        return mismatch
    is_method = int(bool(a._self or b._self))  # 1 if a or b is a method, 0 otherwise

    checkzip = zip(
        a.params[is_method:] + [a.return_type],
        b.params[is_method:] + [b.return_type],
    )
    parts = [test(a, b) for a, b in checkzip]
    return parts


def match_type(a: T, b: T) -> Literal[True] | Mismatch:
    mismatch = Mismatch("type", a, b)

    if isanyofinstance((a, b), AnyType):
        return mismatch

    if isanyofinstance((a, b), NeverType):
        unify_never(a, b)
        return True

    match a, b:
        case NumberType() as a, NumberType() as b:
            if a.typ != b.typ:
                return mismatch
        case ListType() as a, ListType() as b:
            if not match_type(a.content, b.content):
                return mismatch
        case FunctionType() as a, FunctionType() as b:
            checked = _check_func(a, b, match_type, mismatch)
            if isinstance(checked, Mismatch):
                return checked
            return True if all(checked) else mismatch
        case VarType() as a, VarType() as b:
            if a._name != b._name or a.fingerprint != b.fingerprint:
                return mismatch
        case _:
            if a != b:
                return mismatch

    return True


def unify_type(a: T, b: T) -> T | Mismatch:
    mismatch = Mismatch("type", a, b)

    if isinstance(a, AnyType):
        return AnyType()

    if isanyofinstance((a, b), NeverType):
        return unify_never(a, b)

    match a, b:
        case NumberType() as a, NumberType() as b:
            if b.typ == "Num" and a.typ == "Int":
                return mismatch
            return a
        case ListType() as a, ListType() as b:
            content = unify_type(a.content, b.content)
            if not content:
                return mismatch
            return ListType(content=content, _meta=a._meta | b._meta)
        case FunctionType() as a, FunctionType() as b:
            checked = _check_func(a, b, unify_type, mismatch)
            if isinstance(checked, Mismatch):
                return checked

            is_method = int(bool(a._self or b._self))
            return a.edit(
                params=a.params[:is_method] + checked[:-1], return_type=checked[-1]
            )
        case _:
            matched = match_type(a, b)
            if not matched:
                return mismatch
            return a


def match_dim(a: T, b: T) -> Literal[True] | Mismatch:
    """This function should only be called if 'match_type' has already been used successfully."""
    mismatch = Mismatch("dimension", a, b)

    if isanyofinstance((a, b), NeverType):
        unify_never(a, b)
        return True

    match a, b:
        case ListType() as a, ListType() as b:
            if not match_dim(a.content, b.content):
                return mismatch
        case FunctionType() as a, FunctionType() as b:
            checked = _check_func(a, b, match_dim, mismatch)
            if isinstance(checked, Mismatch):
                return checked
            return True if all(checked) else mismatch
        case _:
            ad = a.dim.value if isinstance(a.dim, Expression) else a.dim
            bd = b.dim.value if isinstance(b.dim, Expression) else b.dim
            return mismatch if ad != bd else True
    return True


def unify_dim(a: T, b: T) -> T | Mismatch:
    """This function should only be called if 'unify_type' has already been used successfully."""
    mismatch = Mismatch("dimension", a, b)

    if isanyofinstance((a, b), NeverType):
        return unify_never(a, b)

    match a, b:
        case ListType() as a, ListType() as b:
            content = unify_dim(a.content, b.content)
            if not content:
                return mismatch
            return ListType(content=content, _meta=a._meta | b._meta, dim=content.dim)
        case FunctionType() as a, FunctionType() as b:
            checked = _check_func(a, b, unify_dim, mismatch)
            if isinstance(checked, Mismatch):
                return checked

            is_method = int(bool(a._self or b._self))
            return a.edit(
                params=a.params[:is_method] + checked[:-1], return_type=checked[-1]
            )
        case _:
            ad = a.dim.value if isinstance(a.dim, Expression) else a.dim
            bd = b.dim.value if isinstance(b.dim, Expression) else b.dim
            if isinstance(ad, AnyDim):
                return a
            return mismatch if ad != bd else a
