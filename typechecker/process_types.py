from astnodes import AstNode, Identifier, Unit
from classes import Env, ModuleMeta
from exceptions import Exceptions
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

        return NumberType(typ="Float", dimension=self.dimension(node, env=env))
