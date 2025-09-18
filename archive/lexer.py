import re
from dataclasses import dataclass


@dataclass
class Token:
    type: str
    value: str
    span: tuple[int, int]


source = open("test.und", "r").read()


table = {
    line.split(":")[0].strip(): re.compile(line.split(":", 1)[1].strip(" \n"))
    for line in open("tokens.lex", "r", encoding="utf-8").readlines()
    if re.match(r"[a-zA-Z]+!?\s*:\s*", line)
}

tokens = []

i = 0
while i < len(source):
    matches = [
        Token(type=name, value=match.group(), span=(match.start(), match.end()))
        for name, pattern in table.items()
        if (match := re.match(pattern, source[i:]))
    ]
    if matches:
        if len(matches) > 1:
            print("Ambiguous token:", matches)
        tokens.append(matches[0])
        i += len(matches[0].value)
    else:
        break

print(tokens)
