import re
from importlib import resources
from pathlib import Path
from typing import Iterable

STDLIB_PATH: Path = Path(next(iter(resources.files("numerobis.stdlib")._paths)))  # type: ignore

camel2snake_pattern = re.compile(r"(?<!^)(?=[A-Z])")


def isanyofinstance(objs: Iterable, *types):
    return any(isinstance(obj, types) for obj in objs)


def isallofinstance(objs: Iterable, *types):
    return all(isinstance(obj, types) for obj in objs)
