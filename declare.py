import uuid

from typechecker.types import FunctionType, NeverType, NoneType, StrType, T

names: dict[str, T] = {
    "echo": FunctionType(
        params=[NeverType()],
        return_type=NoneType(),
        param_names=["value"],
        param_addrs=[f"value-{uuid.uuid4()}"],
        _name="echo",
    ),
    "input": FunctionType(
        params=[StrType()],
        return_type=StrType(),
        param_names=["prompt"],
        param_addrs=[f"prompt-{uuid.uuid4()}"],
        _name="input",
    ),
}
