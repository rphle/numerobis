from dataclasses import dataclass, field


@dataclass
class Location:
    line: int = -1
    col: int = -1
    start: int = -1
    end: int = -1


@dataclass
class Token:
    type: str
    value: str
    loc: Location = field(default_factory=lambda: Location(), repr=False)

    def __bool__(self):
        return True
