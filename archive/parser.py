import json
from itertools import batched
from pprint import pprint

from lark import Lark, Token, Transformer, Tree, v_args


def _resolve_unary(chain):
    if not chain:
        return ""
    return ("-" if chain.count("-") % 2 else "") + chain[-1]


@v_args(inline=True)
class ASTGenerator(Transformer):
    def _make_annotation(self, annotation):
        if annotation and (ann := annotation.children[1]):
            name = self.name(ann, type_="annotation")
            return name

    def start(self, *children):
        return list(children)

    def name(self, token, type_="name"):
        return {
            "type": type_,
            "value": token.value,
            "span": [token.start_pos, token.end_pos],
        }

    def boolean(self, token):
        return {
            "type": "boolean",
            "value": token.value == "true",
            "span": [token.start_pos, token.end_pos],
        }

    def pos(self, _add: Token, value: dict):
        value["span"][0] = _add.start_pos
        value["value"] = _resolve_unary(_add.value + value["value"])
        return value

    def neg(self, _sub: Token, value: dict):
        value["span"][0] = _sub.start_pos
        value["value"] = _resolve_unary(_sub.value + value["value"])
        return value

    def float(self, value: Token):
        return {
            "type": "float",
            "value": value.value,
            "span": [value.start_pos, value.end_pos],
        }

    def integer(self, value: Token):
        return {
            "type": "integer",
            "value": value.value,
            "span": [value.start_pos, value.end_pos],
        }

    def arith(self, left: dict, op: Token, right: dict):
        return {
            "type": "arith",
            "left": left,
            "op": self.name(op, "operator"),
            "right": right,
            "span": [left["span"][0], right["span"][1]],
        }

    def comp(self, *args):
        """
        Handle chained comparison operators like: a < b <= c > d.
        Converts chains into logical AND expressions:
        a < b <= c becomes (a < b) && (b <= c)
        """

        def make_comp(left, op, right):
            return {
                "type": "comp",
                "op": self.name(op, "operator"),
                "left": left,
                "right": right,
                "span": [left["span"][0], right["span"][1]],
            }

        if len(args) == 3:
            return make_comp(args[0], args[1], args[2])

        chainable_ops = {"<", "<=", ">", ">="}
        equality_ops = {"==", "!="}
        operators = [str(args[i]) for i in range(1, len(args), 2)]
        all_chainable = all(op in chainable_ops for op in operators)
        all_equality = all(op in equality_ops for op in operators)

        expr = make_comp(args[0], args[1], args[2])

        if all_chainable or all_equality:
            # Build nested logical AND chain with left linking
            for i in range(3, len(args), 2):
                next_comp = make_comp(args[i - 1], args[i], args[i + 1])
                expr = make_comp(expr, args[i], next_comp)
        else:
            # Build nested comparison chain without left linking
            for i in range(3, len(args), 2):
                expr = make_comp(expr, args[i], args[i + 1])

        return expr

    def variable(self, name: Token, annotation: Tree, _assign: Token, value: dict):
        return {
            "type": "variable",
            "name": self.name(name),
            "annotation": self._make_annotation(annotation),
            "value": value,
            "span": [name.start_pos, value["span"][1]],
        }

    def block(self, lbrace: Token, body: Tree, rbrace: Token):
        return {
            "type": "block",
            "children": body.children,
            "span": [lbrace.start_pos, rbrace.end_pos],
        }

    def function(
        self,
        name: Token,
        _lparen: Token,
        params: Tree,
        _rparen: Token,
        annotation: Tree,
        _assign: Token,
        body: dict,
    ):
        params_list = [
            {
                "name": self.name(param),
                "annotation": self._make_annotation(annotation),
                "default": default if default else None,
            }
            for param, annotation, default in batched(params.children, 3)
        ]
        return {
            "type": "function",
            "name": self.name(name) if name else None,
            "params": params_list,
            "annotation": self._make_annotation(annotation),
            "body": body,
            "span": [name.start_pos if name else _lparen.start_pos, body["span"][1]],
        }

    def call(self, name, _lparen, args, _rparen):
        return {
            "type": "call",
            "name": name,
            "args": [
                a | ({"name": n.value if n else None})
                for n, a in batched(args.children, 2)
            ],
            "span": [name["span"][0], _rparen.end_pos],
        }

    def conditional(
        self,
        _if: Token,
        condition: Tree,
        _then: Token,
        then_branch: dict,
        _else: Token | None,
        else_branch: dict | None = None,
    ):
        return {
            "type": "conditional",
            "condition": condition,
            "then_branch": then_branch,
            "else_branch": else_branch,
            "span": [
                _if.start_pos,
                else_branch["span"][1] if else_branch else then_branch["span"][1],
            ],
        }


if __name__ == "__main__":
    grammar = open("grammar.lark", "r").read()
    parser = Lark(grammar, parser="earley", maybe_placeholders=True, lexer="standard")
    source = """
    1-1
    x: lol = {
        1 + 2
        3--4
    }
    (x: haha, y: beep, z): boop = {
        1+1
    }
    if true then beep else boop

    if true then {
        beep
        echo(1,a=2)
    } else {
        boop
    }
    """
    # source = "3--4"
    tree = parser.parse(source)
    print("INPUT:")
    print(source)
    print("=" * 80)
    pprint(tree)
    print("=" * 80)
    ast = ASTGenerator().transform(tree)
    pprint(ast)
    with open("ast.json", "w") as f:
        json.dump(ast, f, indent=2)
