def ensuresuffix(s: str, ch: str) -> str:
    return s if s.endswith(ch) else s + ch


def mthd(name, *args):
    return f"{args[0]}->methods->{name}({', '.join(args)})"
