from astnodes import AstNode, Call, Identifier, Unit
from classes import Env, ModuleMeta
from exceptions import Exceptions, uTypeError
from typechecker.analysis import analyze
from typechecker.types import AnyType, NumberType, T, types


class Processor:
    def __init__(
        self,
        module: ModuleMeta,
    ):
        self.module = module
        self.errors = Exceptions(module=module)

        self.analyze = analyze(module)

    def unit(self, node, env: Env):
        return self.analyze("unit")(node, env)

    def dimension(self, node, env: Env):
        return self.analyze("dimension")(node, env)

    def type(self, node: list[AstNode | Unit], env: Env) -> T:
        if (
            len(node) == 1
            and isinstance(node[0], Identifier)
            and node[0].name in types.keys()
        ):
            return AnyType(node[0].name)
        elif (
            len(node) == 1
            and isinstance(node[0], Call)
            and isinstance(node[0].callee, Identifier)
            and node[0].callee.name in types.keys()
        ):
            match node[0].callee.name:
                case "Float" | "Int":
                    if len(node[0].args) != 1:
                        self.errors.throw(
                            uTypeError,
                            f"Invalid number of parameters for '{node[0].callee.name}'",
                            loc=node[0].loc,
                        )
                    return NumberType(
                        typ=node[0].callee.name,
                        dimension=self.dimension(node[0].args[0].value, env=env),
                    )
                case _:
                    self.errors.throw(
                        uTypeError,
                        f"'{node[0].callee.name}' cannot be parameterized",
                        loc=node[0].loc,
                    )

        return NumberType(typ="Float", dimension=self.dimension(node, env=env))
