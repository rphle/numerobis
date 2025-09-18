from dataclasses import dataclass


@dataclass
class Location:
    line: int
    col: int
    start: int
    end: int


@dataclass
class Token:
    type: str
    value: str
    loc: Location

    def __bool__(self):
        return True


@dataclass
class Tree:
    type: str
    children: list["Tree | Token"]
    loc: Location

    def __bool__(self):
        return True
