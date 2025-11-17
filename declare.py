from typechecker.types import AnyType, FunctionType, NoneType, StrType, T

names: dict[str, T] = {
    "echo": FunctionType(
        params=[AnyType()],
        return_type=NoneType(),
        param_names=["value"],
        _name="echo",
    ),
    "input": FunctionType(
        params=[StrType()],
        return_type=StrType(),
        param_names=["prompt"],
        _name="input",
    ),
}
