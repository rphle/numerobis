from astnodes import AstNode, Call, Identifier, Unit
from classes import ModuleMeta
from environment import Env
from exceptions.exceptions import Exceptions
from typechecker.analysis import analyze
from typechecker.types import AnyType, ListType, NumberType, T, types


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
            if node[0].name in ["Int", "Float"]:
                return NumberType(
                    typ=node[0].name,  # type: ignore
                    dimensionless=True,
                    dimension=[],
                )
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
                        self.errors.invalidParameterNumber(node[0])
                    return NumberType(
                        typ=node[0].callee.name,
                        dimension=self.dimension(node[0].args[0].value, env=env),
                    )
                case "List":
                    if len(node[0].args) != 1:
                        self.errors.invalidParameterNumber(node[0])
                    assert isinstance(node[0].args[0].value, Unit)
                    return ListType(
                        content=self.type(node[0].args[0].value.unit, env=env)
                    )
                case _:
                    self.errors.throw(504, name=node[0].callee.name, loc=node[0].loc)

        return NumberType(
            typ="Float",
            dimension=self.dimension(node, env=env),
            _meta={"#dimension-only": True},
        )
