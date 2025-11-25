import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional


@dataclass
class ErrorMessage:
    code: str
    type: str
    message: str
    help: Optional[str] = None


@lru_cache(maxsize=None)
def parse(path: str) -> dict[str, ErrorMessage]:
    source = open(path, "r").readlines()
    items = []

    for line in source:
        header = re.match(r"\[ \s* (E\d{3} \s* / \s* \w+) \s* \]", line, re.VERBOSE)
        if header:
            items.append([x.strip() for x in header.group(1).split("/")])
        elif not items:
            raise SyntaxError("Must start with a valid header")
        elif line.strip():
            if len(items[-1]) == 4:
                raise ValueError("An item may not have more than two fields")
            items[-1].append(line.strip())

    messages = {fields[0]: ErrorMessage(*fields) for fields in items}

    return messages
