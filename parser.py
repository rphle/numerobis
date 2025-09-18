from classes import Location, Token, Tree
from lexer import LexToken


class Completed(Exception):
    pass


class State:
    i: int
    grammar: dict
    max: int

    def __init__(self, i: int, grammar: dict, max: int = 0):
        self.i = i
        self.grammar = grammar
        self.max = max

    def step(self, n: int = 1):
        self.i += n
        self.max = max(self.i, self.max)


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
}  # type: ignore


def parse(stream: list[LexToken]):
    ast = stream
    start = 0
    state = State(i=0, grammar=grammar)

    while True:
        state.i = start
        tree = []
        converged = list(grammar.keys())
        completed = False

        while True:
            matches = {}
            for name, pttrn in grammar.items():
                if name.startswith("$") or name not in converged:
                    continue
                if match := pttrn.match(ast[state.i], state=state):
                    matches[name] = match

            if matches:
                tree.append(matches)
                converged = [x for x in converged if x in tuple(matches.keys())]
                if state.i + 1 < len(ast):
                    state.step()
                else:
                    completed = True
                    break
            else:
                if len(converged) != 1 or len(tree) != len(grammar[converged[0]]):
                    converged = None
                    print("[NO MATCH FOUND]")
                break

        if completed:
            print("[COMPLETED]")
            break

        if converged is not None:
            tree = [step[converged[0]] for step in tree]
            tree = Tree(
                type=converged[0],
                children=tree,
                loc=Location(
                    line=tree[0].loc.line,
                    col=tree[0].loc.col,
                    start=tree[0].loc.start,
                    end=tree[-1].loc.end,
                ),
            )
            print(tree)
            print("=" * 80)

            ast = [tree] + ast[state.i :]
        else:
            break
