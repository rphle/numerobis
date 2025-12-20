import re
from typing import Iterable

camel2snake_pattern = re.compile(r"(?<!^)(?=[A-Z])")


def isanyofinstance(objs: Iterable, *types):
    return any(isinstance(obj, types) for obj in objs)


def isallofinstance(objs: Iterable, *types):
    return all(isinstance(obj, types) for obj in objs)
