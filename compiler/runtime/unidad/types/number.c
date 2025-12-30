#include "../values.h"
#include "bool.h"
#include <glib.h>
#include <math.h>

static const ValueMethods _number_methods;

static inline Value *_create_value(Number *n) {
  Value *v = g_new(Value, 1);
  v->type = VALUE_NUMBER;
  v->number = n;
  v->methods = &_number_methods;
}

Value *int__init__(gint64 x) {
  Number *n = g_new(Number, 1);
  n->kind = NUM_INT64;
  n->i64 = x;
  return _create_value(n);
}

Value *float__init__(gdouble x) {
  Number *n = g_new(Number, 1);
  n->kind = NUM_DOUBLE;
  n->f64 = x;
  return _create_value(n);
}

static Value *number__bool__(Value *self) {
  bool result = false;
  switch (self->number->kind) {
  case NUM_INT64:
    result = self->number->i64 != 0;
    break;
  case NUM_DOUBLE:
    result = self->number->f64 != 0.0;
    break;
  }
  return bool__init__(result);
}

Value *number__neg__(Value *self) {
  Number *n = g_new(Number, 1);
  n->kind = self->number->kind;

  if (n->kind == NUM_INT64) {
    n->i64 = -(self->number->i64);
  } else {
    n->f64 = -(self->number->f64);
  }

  Value *v = g_new(Value, 1);
  v->type = VALUE_NUMBER;
  v->number = n;
  v->methods = self->methods;
  return v;
}

static int number_cmp(const Number *a, const Number *b) {
  // same type
  if (a->kind == b->kind) {
    if (a->kind == NUM_INT64)
      return (a->i64 > b->i64) - (a->i64 < b->i64);
    return (a->f64 > b->f64) - (a->f64 < b->f64);
  }

  // mixed types
  gint64 iv = (a->kind == NUM_INT64) ? a->i64 : b->i64;
  gdouble fv = (a->kind == NUM_DOUBLE) ? a->f64 : b->f64;
  int flip = (a->kind == NUM_DOUBLE) ? -1 : 1;

  if (isnan(fv))
    return 0;

  gdouble diff = (gdouble)iv - fv;
  if (diff != 0.0)
    return flip * ((diff > 0.0) - (diff < 0.0));

  return 0;
}

static Value *number__lt__(Value *a, Value *b) {
  return bool__init__(number_cmp(a->number, b->number) < 0);
}
static Value *number__le__(Value *a, Value *b) {
  return bool__init__(number_cmp(a->number, b->number) <= 0);
}
static Value *number__gt__(Value *a, Value *b) {
  return bool__init__(number_cmp(a->number, b->number) > 0);
}
static Value *number__ge__(Value *a, Value *b) {
  return bool__init__(number_cmp(a->number, b->number) >= 0);
}
static Value *number__eq__(Value *a, Value *b) {
  return bool__init__(number_cmp(a->number, b->number) == 0);
}

static const ValueMethods _number_methods = {
    .__bool__ = number__bool__,
    .__lt__ = number__lt__,
    .__le__ = number__le__,
    .__gt__ = number__gt__,
    .__ge__ = number__ge__,
    .__eq__ = number__eq__,
    .__neg__ = number__neg__,
};
