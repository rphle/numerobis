from typechecker.types import FunctionSignature, NodeType, NoneT

names = {
    "echo": NodeType(
        typ="Function",
        meta=FunctionSignature(
            params=[NodeType(typ="Any")],
            return_type=NoneT,
            name="echo",
            param_names=["value"],
        ),
    )
}
