#ifndef NUMEROBIS_METHODS_H
#define NUMEROBIS_METHODS_H

#include "../exceptions/throw.h"

#include <stdbool.h>

typedef struct Value Value;
typedef const Location *LocRef;

typedef struct {
  Value (*__bool__)(Value self);
  bool (*__cbool__)(Value self);
  Value (*__add__)(Value self, Value other);
  Value (*__sub__)(Value self, Value other);
  Value (*__mul__)(Value self, Value other);
  Value (*__div__)(Value self, Value other, LocRef loc);
  Value (*__pow__)(Value self, Value other, LocRef loc);
  Value (*__mod__)(Value self, Value other);
  Value (*__dadd__)(Value self, Value other);
  Value (*__dsub__)(Value self, Value other);
  Value (*__intdiv__)(Value self, Value other);
  Value (*__lt__)(Value self, Value other);
  Value (*__le__)(Value self, Value other);
  Value (*__gt__)(Value self, Value other);
  Value (*__ge__)(Value self, Value other);
  Value (*__eq__)(Value self, Value other);
  Value (*__neg__)(Value self);
  Value (*__getitem__)(Value self, Value index);
  Value (*__setitem__)(Value self, Value index, Value value);
  Value (*__getslice__)(Value _self, Value _start, Value _stop, Value _step);
  Value (*__str__)(Value self);
  Value (*__int__)(Value self);
  Value (*__num__)(Value self);
} ValueMethods;

extern const ValueMethods *NUMEROBIS_METHODS[8];

#endif
