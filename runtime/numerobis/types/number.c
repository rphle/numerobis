#include "number.h"
#include "../units/eval.h"
#include "../values.h"
#include "bool.h"
#include "methods.h"
#include "str.h"
#include <glib.h>
#include <math.h>
#include <stdbool.h>
#include <stdint.h>

typedef long (*binop_i64)(long, long);
typedef double (*binop_f64)(double, double);

static const ValueMethods _number_methods;

Value int__init__(long x, const uint64_t unit) {
  Value v;
  v.type = VALUE_NUMBER;
  v.number.kind = NUM_INT64;
  v.number.i64 = x;
  v.number.unit = unit;
  return v;
}

Value num__init__(double x, const uint64_t unit) {
  Value v;
  v.type = VALUE_NUMBER;
  v.number.kind = NUM_DOUBLE;
  v.number.f64 = x;
  v.number.unit = unit;
  return v;
}

static Value number__bool__(Value self) {
  bool result = false;
  switch (self.number.kind) {
  case NUM_INT64:
    result = self.number.i64 != 0;
    break;
  case NUM_DOUBLE:
    result = self.number.f64 != 0.0;
    break;
  }
  return bool__init__(result);
}

static bool number__cbool__(Value self) {
  switch (self.number.kind) {
  case NUM_INT64:
    return self.number.i64 != 0;
  case NUM_DOUBLE:
    return self.number.f64 != 0.0;
  }
  return false;
}

Value number__neg__(Value self) {
  if (self.number.kind == NUM_INT64)
    return int__init__(-(self.number.i64), self.number.unit);
  return num__init__(-(self.number.f64), self.number.unit);
}

// Comparisons

static int number_cmp(const Number *a, const Number *b) {
  if (a->kind == b->kind) {
    if (a->kind == NUM_INT64)
      return (a->i64 > b->i64) - (a->i64 < b->i64);
    return (a->f64 > b->f64) - (a->f64 < b->f64);
  }
  long iv = (a->kind == NUM_INT64) ? a->i64 : b->i64;
  double fv = (a->kind == NUM_DOUBLE) ? a->f64 : b->f64;
  int flip = (a->kind == NUM_DOUBLE) ? -1 : 1;
  if (isnan(fv))
    return 0;
  double diff = (double)iv - fv;
  if (diff != 0.0)
    return flip * ((diff > 0.0) - (diff < 0.0));
  return 0;
}

static inline Value number__lt__(Value a, Value b) {
  return bool__init__(number_cmp(&a.number, &b.number) < 0);
}
static inline Value number__le__(Value a, Value b) {
  return bool__init__(number_cmp(&a.number, &b.number) <= 0);
}
static inline Value number__gt__(Value a, Value b) {
  return bool__init__(number_cmp(&a.number, &b.number) > 0);
}
static inline Value number__ge__(Value a, Value b) {
  return bool__init__(number_cmp(&a.number, &b.number) >= 0);
}
static inline Value number__eq__(Value a, Value b) {
  return bool__init__(number_cmp(&a.number, &b.number) == 0);
}

// Binary operators

static inline double number_as_double(const Number *n) {
  return n->kind == NUM_DOUBLE ? n->f64 : (double)n->i64;
}

static Value number_binop(Value a, Value b, binop_i64 iop, binop_f64 fop,
                          OpKind kind) {
  Number *na = &a.number;
  Number *nb = &b.number;

  uint64_t uha = na->unit;
  uint64_t uhb = nb->unit;

  const Unit *ua = unit_get(uha);
  const Unit *ub = unit_get(uhb);

  bool dimless =
      (is_one(ua) && ua->scalar == 1.0) && (is_one(ub) && ub->scalar == 1.0);

  uint64_t unit = NUMEROBIS_UNIT_ONE_HASH;

  bool _x_defined = false;
  bool _y_defined = false;
  double x = 0, y = 0;

  switch (kind) {
  case OP_ADD:
  case OP_SUB:
    unit = uha;

    // if nb is dimensionless and ua has a scalar, convert nb into ua's space
    if (!dimless && (is_one(ub) && ub->scalar == 1.0) &&
        (is_one(ua) && ua->scalar != 1.0)) {
      double nb_val = nb->kind == NUM_INT64 ? (double)nb->i64 : nb->f64;
      double na_val = na->kind == NUM_INT64 ? (double)na->i64 : na->f64;
      double converted = nb_val / ua->scalar;
      double result = kind == OP_ADD ? na_val + converted : na_val - converted;

      if (result == (double)(long)result && na->kind != NUM_DOUBLE &&
          nb->kind != NUM_DOUBLE)
        return int__init__((long)result, unit);
      return num__init__(result, unit);
    }
    break;
  case OP_MUL:
    unit = !dimless ? unit_mul(ua, ub, false) : NUMEROBIS_UNIT_ONE_HASH;
    break;
  case OP_DIV:
    unit = !dimless ? unit_mul(ua, ub, true) : NUMEROBIS_UNIT_ONE_HASH;
    break;
  case OP_POW: {
    double exp = (nb->kind == NUM_DOUBLE) ? nb->f64 : (double)nb->i64;
    unit = !dimless ? unit_pow(ua, exp) : NUMEROBIS_UNIT_ONE_HASH;
    break;
  }
  case OP_DADD:
  case OP_DSUB:
    x = eval_number(na, &uha);
    y = eval_number(nb, &uha);
    x = fop(x, y);
    y = 0;
    x = eval_unit(ua, x, EVAL_NORMAL);
    _x_defined = true;
    _y_defined = true;
    unit = uha;
    break;
  default:
    unit = NUMEROBIS_UNIT_ONE_HASH;
    break;
  }

  if (na->kind == NUM_DOUBLE || nb->kind == NUM_DOUBLE || (kind == OP_DIV)) {
    if (!_x_defined)
      x = number_as_double(na);
    if (!_y_defined)
      y = number_as_double(nb);
    return num__init__(fop(x, y), unit);
  }
  return int__init__(
      iop(_x_defined ? (long)x : na->i64, _y_defined ? (long)y : nb->i64),
      unit);
}

static inline long i_add(long a, long b) { return a + b; }
static inline long i_sub(long a, long b) { return a - b; }
static inline long i_mul(long a, long b) { return a * b; }
static inline long i_div(long a, long b) { return a / b; }
static inline long i_pow(long a, long b) {
  return (long)pow((double)a, (double)b);
}
static inline long i_mod(long a, long b) {
  return (long)fmod((double)a, (double)b);
}

static inline double f_add(double a, double b) { return a + b; }
static inline double f_sub(double a, double b) { return a - b; }
static inline double f_mul(double a, double b) { return a * b; }
static inline double f_div(double a, double b) { return a / b; }
static inline double f_pow(double a, double b) { return pow(a, b); }
static inline double f_mod(double a, double b) { return fmod(a, b); }

static inline Value number__add__(Value a, Value b) {
  return number_binop(a, b, i_add, f_add, OP_ADD);
}
static inline Value number__sub__(Value a, Value b) {
  return number_binop(a, b, i_sub, f_sub, OP_SUB);
}
static inline Value number__mul__(Value a, Value b) {
  return number_binop(a, b, i_mul, f_mul, OP_MUL);
}
static inline Value number__div__(Value a, Value b) {
  return number_binop(a, b, i_div, f_div, OP_DIV);
}
static inline Value number__pow__(Value a, Value b) {
  return number_binop(a, b, i_pow, f_pow, OP_POW);
}
static inline Value number__mod__(Value a, Value b) {
  return number_binop(a, b, i_mod, f_mod, OP_MOD);
}
static inline Value number__dadd__(Value a, Value b) {
  return number_binop(a, b, i_add, f_add, OP_DADD);
}
static inline Value number__dsub__(Value a, Value b) {
  return number_binop(a, b, i_sub, f_sub, OP_DSUB);
}

// Conversions

static Value number__str__(Value val) {
  return str__init__(print_number(&val.number));
}

static Value number__int__(Value self) {
  Number *n = &self.number;
  return (n->kind == NUM_INT64) ? self : int__init__((long)n->f64, n->unit);
}

static Value number__num__(Value self) {
  Number *n = &self.number;
  return (n->kind == NUM_DOUBLE) ? self : num__init__((double)n->i64, n->unit);
}

Value number__convert__(Value self, const uint64_t target) {
  Number *n = &self.number;
  double value = n->kind == NUM_INT64 ? (double)(n->i64) : n->f64;
  Unit *u = unit_get(target);
  bool dimless = (is_one(u) && u->scalar == 1.0);

  if (dimless) {
    value = eval_number(n, NULL);
    Unit *src = unit_get(n->unit);
    value *= src->scalar;
  }

  if (n->kind == NUM_INT64)
    return int__init__((long)value, target);
  return num__init__(value, target);
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
    .__dadd__ = number__dadd__,
    .__dsub__ = number__dsub__,
    .__lt__ = number__lt__,
    .__le__ = number__le__,
    .__gt__ = number__gt__,
    .__ge__ = number__ge__,
    .__eq__ = number__eq__,
    .__neg__ = number__neg__,
    .__str__ = number__str__,
    .__int__ = number__int__,
    .__num__ = number__num__,
};

void number_methods_init(void) {
  NUMEROBIS_METHODS[VALUE_NUMBER] = &_number_methods;
}
