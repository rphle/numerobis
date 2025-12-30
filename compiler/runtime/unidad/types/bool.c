#include "../values.h"
#include <glib.h>
#include <stdbool.h>

static const ValueMethods _bool_methods;

Value *bool__init__(bool x) {
  Value *v = g_new(Value, 1);
  v->type = VALUE_BOOL;
  v->boolean = x;
  v->methods = &_bool_methods;
}

Value *bool__bool__(Value *self) { return self; }

Value *bool__eq__(Value *self, Value *other) {
  return bool__init__(self->boolean == other->boolean);
}

static const ValueMethods _bool_methods = {
    .__bool__ = bool__bool__,
    .__eq__ = bool__eq__,
};
