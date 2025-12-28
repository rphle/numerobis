from typechecker.types import UType


def ensuresuffix(s: str, ch: str) -> str:
    return s if s.endswith(ch) else s + ch


def _getitem_(index: str, iterable: str, item_c_type: str, iterable_type: str) -> str:
    text = f"{iterable_type}__getitem__({iterable}, {index})"

    if iterable_type == "list":
        text = f"UNBOX({item_c_type}{star(item_c_type)}, {text})"
    return text


def star(typ: str | UType) -> str:
    if isinstance(typ, UType):
        return "*" if typ.name("Str", "List") else ""
    return "*" if typ.lower() in ["gstring", "garray", "str", "list", "array"] else ""
