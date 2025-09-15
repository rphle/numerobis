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
    def _make_name(self, token, _type="name"):
        return {
            "_type": _type,
            "value": token.value,
            "span": [token.start_pos, token.end_pos],
        }

    def _make_annotation(self, annotation):
        if annotation and (ann := annotation.children[1]):
            name = self._make_name(ann, _type="annotation")
            return name

    def start(self, *children):
        return list(children)

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
            "_type": "expr",
            "type": "float",
            "value": value.value,
            "span": [value.start_pos, value.end_pos],
        }

    def integer(self, value: Token):
        return {
            "_type": "expr",
            "type": "integer",
            "value": value.value,
            "span": [value.start_pos, value.end_pos],
        }

    def bin_op(self, left: dict, op: Token, right: dict):
        return {
            "_type": "expr",
            "type": "bin_op",
            "left": left,
            "op": self._make_name(op),
            "right": right,
            "span": [left["span"][0], right["span"][1]],
        }

    def variable(self, name: Token, annotation: Tree, _assign: Token, value: dict):
        return {
            "_type": "stmt",
            "type": "variable",
            "name": self._make_name(name),
            "annotation": self._make_annotation(annotation),
            "value": value,
            "span": [name.start_pos, value["span"][1]],
        }

    def block(self, lbrace: Token, body: Tree, rbrace: Token):
        return {
            "_type": "expr",
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
                "name": self._make_name(param),
                "annotation": self._make_annotation(annotation),
            }
            for param, annotation in batched(params.children, 2)
        ]
        return {
            "_type": "stmt",
            "type": "function",
            "name": self._make_name(name) if name else None,
            "params": params_list,
            "annotation": self._make_annotation(annotation),
            "body": body,
            "span": [name.start_pos if name else _lparen.start_pos, body["span"][1]],
        }


if __name__ == "__main__":
    grammar = open("grammar.lark", "r").read()
    parser = Lark(grammar, parser="earley", maybe_placeholders=True)
    source = """
    1-1
    x: lol = {
        1 + 2
        3--4
    }
    (x: haha, y: beep, z): boop = {
        1+1
    }
    # if x > 0 > -1 then beep
    """
    source = "if x > 0 > -1 then beep"
    tree = parser.parse(source)
    pprint(tree)
    print("=" * 80)
    ast = ASTGenerator().transform(tree)
    pprint(ast)
    with open("ast.json", "w") as f:
        json.dump(ast, f, indent=2)
