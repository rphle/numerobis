import re
from typing import Any, Optional


class tstr:
    def __init__(
        self,
        value: str,
        *,
        content: dict[str, "str|tstr"] = {},
        meta: dict[str, Any] = {},
    ):
        self.value: str = value
        self.content: dict[str, "str|tstr"] = dict(content)
        self.meta: dict[str, Any] = dict(meta)

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

    def __setitem__(self, key: str, value: "str|tstr"):
        self.content[key] = value

    def __getitem__(self, key: str) -> Optional["str|tstr"]:
        return self.content.get(key)

    def __str__(self) -> str:
        filled = self.value
        for key in sorted(self.content, key=len, reverse=True):
            filled = filled.replace(f"${key}", str(self.content[key]))
        return filled

    def __repr__(self) -> str:
        return f"tstr('{self.value}')"

    def __add__(self, other) -> "tstr":
        if isinstance(other, tstr):
            return tstr(self.value + other.value, content=self.content | other.content)
        elif isinstance(other, str):
            return tstr(self.value + other, content=self.content)
        else:
            raise TypeError(
                f"unsupported operand type(s) for +: 'tstr' and {type(other).__name__}"
            )
