"""Unit and dimension expression nodes for dimensional analysis.

Represents algebraic expressions of units and dimensions as trees.
"""

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from math import prod
from typing import Optional

from .core import Identifier, UnitNode


@dataclass(frozen=True)
class Product(UnitNode):
    values: list[UnitNode]

    def __post_init__(self):
        if self.values:
            object.__setattr__(
                self, "loc", self.values[0].loc.merge(self.values[-1].loc)
            )

    def add(self, other: UnitNode):
        self.values.append(other)
        object.__setattr__(self, "loc", self.values[0].loc.merge(self.values[-1].loc))

    def __getitem__(self, index):
        return self.values[index]

    def __len__(self):
        return len(self.values)

    def __str__(self):
        return " * ".join(
            str(value) if not isinstance(value, Sum) else f"({value})"
            for value in self.values
        )

    def __eq__(self, other):
        if not isinstance(other, Product):
            return False
        return Counter(self.values) == Counter(other.values)

    def __bool__(self):
        return any(value for value in self.values)

    def __hash__(self):
        return hash(tuple(self.values))

    @staticmethod
    def apply(values):
        return prod(values)


@dataclass(frozen=True)
class Sum(UnitNode):
    values: list[UnitNode]

    def __post_init__(self):
        if self.values:
            object.__setattr__(
                self, "loc", self.values[0].loc.merge(self.values[-1].loc)
            )

    def add(self, other: UnitNode):
        self.values.append(other)
        object.__setattr__(self, "loc", self.values[0].loc.merge(self.values[-1].loc))

    def __getitem__(self, index):
        return self.values[index]

    def __len__(self):
        return len(self.values)

    def __str__(self):
        return " + ".join(
            str(value) if not isinstance(value, Product) else f"({value})"
            for value in self.values
        )

    def __eq__(self, other):
        if not isinstance(other, Sum):
            return False
        return Counter(self.values) == Counter(other.values)

    def __bool__(self):
        return any(value for value in self.values)

    def __hash__(self):
        return hash(tuple(self.values))

    @staticmethod
    def apply(values):
        return sum(values)


@dataclass(frozen=True)
class Expression(UnitNode):
    value: UnitNode

    def __post_init__(self):
        if self.value:
            object.__setattr__(self, "loc", self.value.loc)

    def __str__(self):
        return f"\\[[bold]{self.value}[/bold]]"

    def __eq__(self, other):
        if not isinstance(other, Expression):
            return False
        return self.value == other.value

    def __bool__(self) -> bool:
        return bool(self.value)


@dataclass(frozen=True)
class Scalar(UnitNode):
    value: Decimal
    unit: Optional[Expression] = None
    placeholder: bool = field(default=False, repr=False)

    def __post_init__(self):
        if not isinstance(self.value, Decimal):
            raise TypeError(f"Expected Decimal, got {type(self.value)}")

    def __str__(self):
        value = str(self.value)
        if "." in value:
            value = value.rstrip("0").rstrip(".")
        if self.unit is None:
            return value
        return f"{value} {self.unit}"

    def __eq__(self, other):
        if not isinstance(other, Scalar):
            return False
        return self.value == other.value and self.unit == other.unit

    def __add__(self, other):
        if not isinstance(other, Scalar):
            raise TypeError(f"Cannot add {type(self)} and {type(other)}")
        return Scalar(self.value + other.value, self.unit)


@dataclass(frozen=True)
class Constant(UnitNode):
    name: str

    def __str__(self):
        return f"@{self.name}"

    def __eq__(self, other):
        if not isinstance(other, Constant):
            return False
        return self.name == other.name


@dataclass(frozen=True)
class Neg(UnitNode):
    value: UnitNode

    def __str__(self):
        return f"-{f'({self.value})' if not isinstance(self.value, Scalar) else self.value}"

    def __eq__(self, other):
        if not isinstance(other, Neg):
            return False
        return self.value == other.value


@dataclass(frozen=True)
class Power(UnitNode):
    base: Sum | Product | UnitNode
    exponent: Sum | Product | UnitNode

    def __str__(self):
        base = (
            f"({self.base})"
            if not isinstance(self.base, (Scalar, Identifier))
            else self.base
        )
        exponent = (
            f"({self.exponent})"
            if not isinstance(self.exponent, (Scalar, Identifier))
            else self.exponent
        )
        return f"{base}^{exponent}"

    def __eq__(self, other):
        if not isinstance(other, Power):
            return False
        return self.base == other.base and self.exponent == other.exponent


@dataclass(frozen=True)
class CallArg(UnitNode):
    name: Identifier | None
    value: UnitNode

    def __str__(self):
        return f"{self.name.name + '=' if self.name else ''}{self.value}"


@dataclass(frozen=True)
class Call(UnitNode):
    callee: UnitNode
    args: list[CallArg]

    def __str__(self):
        return f"{self.callee}({', '.join(str(a) for a in self.args)})"

    def __hash__(self):
        return hash(tuple(self.args))


@dataclass(frozen=True)
class One(UnitNode):
    def __str__(self):
        return "1"

    def __eq__(self, other):
        return isinstance(other, One)

    def __bool__(self):
        return False
