import re
from typing import Optional


class tstr:
    def __init__(self, value: str, content: Optional[dict[str, str]] = None):
        self.value: str = value
        self.content: dict[str, str] = dict(content) if content else {}

    def remove(self, *keys: str):
        if not keys:
            keys = tuple(
                key
                for key in re.findall(r"\$\w+", self.value)
                if key not in self.content
            )
        for key in keys:
            self.value = self.value.replace(f"${key}", "")
            del self.content[key]

    def strip(self):
        self.value = self.value.strip()

    def __setitem__(self, key: str, value: str):
        self.content[key] = value

    def __getitem__(self, key: str) -> Optional[str]:
        return self.content.get(key)

    def __str__(self) -> str:
        filled = self.value
        for key, value in self.content.items():
            filled = filled.replace(f"${key}", value)
        return filled

    def __repr__(self) -> str:
        return f"tstr('{self.value}')"

    def __add__(self, other) -> "tstr":
        if isinstance(other, tstr):
            return tstr(self.value + other.value, self.content | other.content)
        elif isinstance(other, str):
            return tstr(self.value + other, self.content)
        else:
            raise TypeError(
                f"unsupported operand type(s) for +: 'tstr' and {type(other).__name__}"
            )
