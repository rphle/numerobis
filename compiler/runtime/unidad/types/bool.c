#include "../values.h"
#include "number.h"
#include "str.h"
#include <glib.h>
#include <stdbool.h>

static const ValueMethods _bool_methods;

Value *bool__init__(bool x) {
  Value *v = g_new(Value, 1);
  v->type = VALUE_BOOL;
  v->boolean = x;
  v->methods = &_bool_methods;
}

static inline Value *bool__bool__(Value *self) { return self; }
static inline bool bool__cbool__(Value *self) { return self->boolean; }

static inline Value *bool__eq__(Value *self, Value *other) {
  return bool__init__(self->boolean == other->boolean);
}

static inline Value *bool__str__(Value *self) {
  str__init__(g_string_new(self->boolean ? "true" : "false"));
}

static inline Value *bool__int__(Value *self) {
  return int__init__(self->boolean ? 1 : 0);
}

static const ValueMethods _bool_methods = {
    .__bool__ = bool__bool__,
    .__cbool__ = bool__cbool__,
    .__eq__ = bool__eq__,
    .__str__ = bool__str__,
    .__int__ = bool__int__,
};
