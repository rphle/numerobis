import re

camel2snake_pattern = re.compile(r"(?<!^)(?=[A-Z])")


def isanyofinstance(objs: tuple, *types):
    return any(isinstance(obj, types) for obj in objs)
