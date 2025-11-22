from typechecker.types import FunctionType, NeverType, NoneType, StrType, T

names: dict[str, T] = {
    "echo": FunctionType(
        params=[NeverType()],
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
