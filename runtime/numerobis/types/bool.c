#include "../units/units.h"
#include "../values.h"
#include "methods.h"
#include "number.h"
#include "str.h"

#include <stdbool.h>

static const ValueMethods _bool_methods;

Value bool__init__(bool x) {
  Value v;
  v.type = VALUE_BOOL;
  v.boolean = x;
  return v;
}

static inline Value bool__bool__(Value self) { return self; }
static inline bool bool__cbool__(Value self) { return self.boolean; }

static inline Value bool__eq__(Value self, Value other) {
  return bool__init__(self.boolean == other.boolean);
}

static inline Value bool__str__(Value self) {
  return str__init__(sdsnew(self.boolean ? "true" : "false"));
}

static inline Value bool__int__(Value self) {
  return int__init__(self.boolean ? 1 : 0, U_ONE);
}

static inline Value bool__num__(Value self) {
  return num__init__(self.boolean ? 1.0 : 0.0, U_ONE);
}

static const ValueMethods _bool_methods = {
    .__bool__ = bool__bool__,
    .__cbool__ = bool__cbool__,
    .__eq__ = bool__eq__,
    .__str__ = bool__str__,
    .__int__ = bool__int__,
    .__num__ = bool__num__,
};

void bool_methods_init(void) { NUMEROBIS_METHODS[VALUE_BOOL] = &_bool_methods; }
