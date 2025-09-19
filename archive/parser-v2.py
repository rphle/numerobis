# type: ignore

from classes import Location, Token, Tree
from lexer import LexToken


class Completed(Exception):
    pass


@dataclass
class Tree:
    type: str
    children: list["Tree | Token"]
    loc: Location

    def __bool__(self):
        return True


class State:
    i: int
    grammar: dict
    max: int
    stack: list

    def __init__(self, i: int, grammar: dict, max: int = 0, stack: list = []):
        self.i = i
        self.grammar = grammar
        self.max = max
        self.stack = stack

    def step(self, n: int = 1):
        self.i += n
        self.max = max(self.i, self.max)

    def add(self, value: str):
        self.stack.append(value)


class Pattern:
    def _transform(self, *values):
        r = []
        for v in values:
            match v:
                case str():
                    r.append(Terminal(v))
                case tuple():
                    r.append(Seq(*v))
                case _:
                    r.append(v)
        return tuple(r)


class Terminal(Pattern):
    def __init__(self, value: str):
        self.value = value

    def match(self, value, state):
        return Token(**value.__dict__) if value.type == self.value else None


class Seq(Pattern):
    def __init__(self, *values):
        self.values = self._transform(*values)

    def match(self, value, state):
        if state.i < len(self.values):
            return self.values[state.i].match(value, state=state)

    def __repr__(self):
        return f"( {', '.join(str(v) for v in self.values)} )"

    def __len__(self):
        return len(self.values)


class OneOf(Pattern):
    def __init__(self, *values):
        self.values = self._transform(*values)

    def match(self, value, state):
        return next(
            (match for x in self.values if (match := x.match(value, state=state))),
            None,
        )

    def __repr__(self):
        return f"oneof[ {', '.join(str(v) for v in self.values)} ]"


class Ref(Pattern):
    def __init__(self, value: str):
        self.value = value

    def match(self, value, state):
        if isinstance(value, Tree) and value.type == self.value:
            return value

        if self.value in state.stack:
            return
        state.add(self.value)
        return grammar[self.value].match(value, state=state)

    def __repr__(self):
        return f"ref[ {str(self.value)} ]"


grammar = {
    "$atom": (OneOf("INTEGER", "FLOAT", "ID"),),
    "$expr": (OneOf(Ref("$atom"), Ref("function_call")),),
    "integer": "INTEGER",
    "float": "FLOAT",
    "identifier": "ID",
    "arithmetic": (
        Ref("$atom"),
        OneOf("MINUS", "PLUS", "TIMES", "DIVIDE", "MOD", "POWER"),
        Ref("$atom"),
    ),
    "function_call": (Ref("$expr"), "LPAREN", "RPAREN"),
}

grammar = {
    n: Seq(p) if not isinstance(p, tuple) else Seq(*p) for n, p in grammar.items()
}


def parse(stream: list[LexToken]):
    ast = stream
    state = State(i=0, grammar=grammar)

    while True:
        state.i = 0
        tree = []
        converged = [name for name in grammar.keys() if not name.startswith("$")]

        while state.i < len(ast):
            matches = {
                name: match
                for name in converged
                if (
                    match := grammar[name].match(
                        ast[state.i], State(**(state.__dict__ | {"stack": [name]}))
                    )
                )
            }

            if matches:
                tree.append(matches)
                converged = list(matches.keys())
                state.step()
            else:
                if len(converged) == 1 and len(tree) == len(grammar[converged[0]]):
                    break
                print("[NO MATCH FOUND]")
                return

        valid_rules = [rule for rule in converged if len(grammar[rule]) == len(tree)]

        if not valid_rules:
            print("[NO MATCH FOUND]")
            return

        rule = valid_rules[0]
        parsed_tree = Tree(
            type=rule,
            children=[step[rule] for step in tree],
            loc=Location(
                line=tree[0][rule].loc.line,
                col=tree[0][rule].loc.col,
                start=tree[0][rule].loc.start,
                end=tree[-1][rule].loc.end,
            ),
        )

        print(parsed_tree)
        print("=" * 80)

        ast = [parsed_tree] + ast[state.i :]

        if len(ast) == 1:
            print("[COMPLETED]")
            break
