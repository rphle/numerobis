def ensuresuffix(s: str, ch: str) -> str:
    return s if s.endswith(ch) else s + ch


def mthd(name, *args):
    return f"{args[0]}->methods->{name}({', '.join(args)})"


def repr_double(s):
    single = "'" + repr('"' + s)[2:]
    return '"' + single[1:-1].replace('"', '\\"').replace("\\'", "'") + '"'
