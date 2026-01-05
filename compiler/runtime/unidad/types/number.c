#include "../values.h"
#include "bool.h"
#include "str.h"
#include <glib.h>
#include <math.h>
#include <stdbool.h>

typedef gint64 (*binop_i64)(gint64, gint64);
typedef gdouble (*binop_f64)(gdouble, gdouble);

static const ValueMethods _number_methods;

static inline Value *_create_value(Number *n) {
  Value *v = g_new(Value, 1);
  v->type = VALUE_NUMBER;
  v->number = n;
  v->methods = &_number_methods;
  return v;
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

static bool number__cbool__(Value *self) {
  switch (self->number->kind) {
  case NUM_INT64:
    return self->number->i64 != 0;
    break;
  case NUM_DOUBLE:
    return self->number->f64 != 0.0;
    break;
  }
}

Value *number__neg__(Value *self) {
  Number *n = g_new(Number, 1);
  n->kind = self->number->kind;

  if (n->kind == NUM_INT64) {
    n->i64 = -(self->number->i64);
  } else {
    n->f64 = -(self->number->f64);
  }

  return _create_value(n);
}

// Comparisons

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

static inline Value *number__lt__(Value *a, Value *b) {
  return bool__init__(number_cmp(a->number, b->number) < 0);
}
static inline Value *number__le__(Value *a, Value *b) {
  return bool__init__(number_cmp(a->number, b->number) <= 0);
}
static inline Value *number__gt__(Value *a, Value *b) {
  return bool__init__(number_cmp(a->number, b->number) > 0);
}
static inline Value *number__ge__(Value *a, Value *b) {
  return bool__init__(number_cmp(a->number, b->number) >= 0);
}
static inline Value *number__eq__(Value *a, Value *b) {
  return bool__init__(number_cmp(a->number, b->number) == 0);
}

// Binary operators
static inline bool number_is_double(const Number *n) {
  return n->kind == NUM_DOUBLE;
}

static inline gdouble number_as_double(const Number *n) {
  return n->kind == NUM_DOUBLE ? n->f64 : (gdouble)n->i64;
}

static Value *number_binop(Value *a, Value *b, binop_i64 iop, binop_f64 fop) {
  Number *na = a->number;
  Number *nb = b->number;

  if (na->kind == NUM_DOUBLE || nb->kind == NUM_DOUBLE) {
    gdouble x = (na->kind == NUM_DOUBLE) ? na->f64 : (gdouble)na->i64;
    gdouble y = (nb->kind == NUM_DOUBLE) ? nb->f64 : (gdouble)nb->i64;
    return float__init__(fop(x, y));
  }

  return int__init__(iop(na->i64, nb->i64));
}

static inline gint64 i_add(gint64 a, gint64 b) { return a + b; }
static inline gint64 i_sub(gint64 a, gint64 b) { return a - b; }
static inline gint64 i_mul(gint64 a, gint64 b) { return a * b; }
static inline gint64 i_div(gint64 a, gint64 b) { return a / b; }
static inline gint64 i_pow(gint64 a, gint64 b) { return pow(a, b); }
static inline gint64 i_mod(gint64 a, gint64 b) { return fmod(a, b); }

static inline gdouble f_add(gdouble a, gdouble b) { return a + b; }
static inline gdouble f_sub(gdouble a, gdouble b) { return a - b; }
static inline gdouble f_mul(gdouble a, gdouble b) { return a * b; }
static inline gdouble f_div(gdouble a, gdouble b) { return a / b; }
static inline gdouble f_pow(gdouble a, gdouble b) { return pow(a, b); }
static inline gdouble f_mod(gdouble a, gdouble b) { return fmod(a, b); }

static inline Value *number__add__(Value *a, Value *b) {
  return number_binop(a, b, i_add, f_add);
}
static inline Value *number__sub__(Value *a, Value *b) {
  return number_binop(a, b, i_sub, f_sub);
}
static inline Value *number__mul__(Value *a, Value *b) {
  return number_binop(a, b, i_mul, f_mul);
}
static inline Value *number__div__(Value *a, Value *b) {
  return number_binop(a, b, i_div, f_div);
}
static inline Value *number__pow__(Value *a, Value *b) {
  return number_binop(a, b, i_pow, f_pow);
}
static inline Value *number__mod__(Value *a, Value *b) {
  return number_binop(a, b, i_mod, f_mod);
}

static Value *number__str__(Value *val) {
  GString *result = g_string_new("");

  Number *n = val->number;
  if (n->kind == NUM_INT64) {
    g_string_printf(result, "%ld", n->i64);
  } else {
    g_string_printf(result, "%g", n->f64);
  }
  return str__init__(result);
}

static Value *number__int__(Value *self) {
  Number *n = self->number;
  if (n->kind == NUM_INT64) {
    return int__init__(n->i64);
  } else {
    return int__init__((gint64)n->f64);
  }
}

static const ValueMethods _number_methods = {
    .__bool__ = number__bool__,
    .__cbool__ = number__cbool__,
    .__add__ = number__add__,
    .__sub__ = number__sub__,
    .__mul__ = number__mul__,
    .__div__ = number__div__,
    .__pow__ = number__pow__,
    .__mod__ = number__mod__,
    .__lt__ = number__lt__,
    .__le__ = number__le__,
    .__gt__ = number__gt__,
    .__ge__ = number__ge__,
    .__eq__ = number__eq__,
    .__neg__ = number__neg__,
    .__str__ = number__str__,
    .__int__ = number__int__,
};
