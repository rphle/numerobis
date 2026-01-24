import random
from dataclasses import dataclass, field, fields

import mmh3


def nodeloc(*nodes):
    return Location(
        line=nodes[0].loc.line,
        col=nodes[0].loc.col,
        end_line=nodes[-1].loc.end_line,
        end_col=nodes[-1].loc.end_col,
    )


@dataclass
class Location:
    line: int = -1
    col: int = -1
    end_line: int = -1
    end_col: int = -1

    checkpoints: dict[str, "Location"] = field(default_factory=dict)

    def merge(self, other: "Location"):
        self.end_line = other.end_line if other.end_line != -1 else self.end_line
        self.end_col = other.end_col if other.end_col != -1 else self.end_col
        return self

    def split(self) -> list["Location"]:
        """
        Split a multi-line position span into individual line positions.
        """
        return [
            Location(
                line=line,
                col=self.col if line == self.line else 1,
                end_line=line,
                end_col=-1 if line != self.end_line else self.end_col,
            )
            for line in range(
                self.line, (self.end_line if self.end_line != -1 else self.line) + 1
            )
        ]

    def _point(self, name: str) -> "Location":
        if name == "start":
            return Location(self.line, self.col, self.line, self.col)

        if name == "end":
            el = self.end_line if self.end_line != -1 else self.line
            ec = self.end_col if self.end_col != -1 else self.col
            return Location(el, ec, el, ec)

        return self.checkpoints[name]

    def span(self, start: str, end: str) -> "Location":
        s = self._point(start)
        e = self._point(end)
        return Location(
            line=s.line,
            col=s.col,
            end_line=e.end_line,
            end_col=e.end_col,
        )


@dataclass
class Token:
    type: str
    value: str
    loc: Location = field(default_factory=lambda: Location(), repr=False, compare=False)

    def __bool__(self):
        return True


@dataclass(kw_only=True, frozen=True)
class AstNode:
    loc: Location = field(default_factory=lambda: Location(), repr=False, compare=False)
    meta: dict = field(default_factory=dict, repr=False, compare=False)

    def hash(self) -> int:
        struct = self._struct()
        return mmh3.hash(str(struct), seed=random.randint(0, 2**32 - 1))

    def _struct(self):
        return (
            self.__class__.__name__,
            tuple((f.name, self._conv(getattr(self, f.name))) for f in fields(self)),
        )

    @classmethod
    def _conv(cls, v):
        if isinstance(v, AstNode):
            return v._struct()
        if isinstance(v, list):
            return tuple(cls._conv(x) for x in v)
        if isinstance(v, dict):
            return tuple((k, cls._conv(v[k])) for k in sorted(v))
        return v

    def __bool__(self):
        return True


@dataclass(kw_only=True, frozen=True)
class UnitNode:
    loc: Location = field(default_factory=lambda: Location(), repr=False, compare=False)


@dataclass(frozen=True)
class Identifier(UnitNode, AstNode):
    name: str

    def __str__(self):
        return self.name

    def __eq__(self, other):
        if not isinstance(other, Identifier):
            return False
        return self.name == other.name
