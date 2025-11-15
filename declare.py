from typechecker.types import AnyType, FunctionType, NoneType, T

names: dict[str, T] = {
    "echo": FunctionType(
        params=[AnyType()],
        return_type=NoneType(),
        param_names=["value"],
        _name="echo",
    )
}
