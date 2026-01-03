import uuid

from typechecker.types import FunctionType, NeverType, NoneType, StrType, T

names: dict[str, T] = {
    "echo": FunctionType(
        params=[NeverType(), StrType()],
        return_type=NoneType(),
        param_names=["value", "end"],
        param_addrs=[f"value-{uuid.uuid4()}", f"end-{uuid.uuid4()}"],
        param_defaults=[None, None],
        _name="echo",
        arity=(1, 2),
    ),
    "input": FunctionType(
        params=[StrType()],
        return_type=StrType(),
        param_names=["prompt"],
        param_addrs=[f"prompt-{uuid.uuid4()}"],
        _name="input",
    ),
}
