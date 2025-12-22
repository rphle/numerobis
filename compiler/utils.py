def ensuresuffix(s: str, ch: str) -> str:
    return s if s.endswith(ch) else s + ch
