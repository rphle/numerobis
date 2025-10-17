import re

camel2snake_pattern = re.compile(r"(?<!^)(?=[A-Z])")

operators = {
    "add": "+",
    "sub": "-",
    "mul": "*",
    "div": "/",
    "pow": "^",
    "mod": "%",
    "intdiv": "//",
}
