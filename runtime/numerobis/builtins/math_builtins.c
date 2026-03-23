#include "math_builtins.h"

#include "../extern.h"
#include "../types/number.h"
#include "../units/units.h"
#include "../values.h"

#include <glib.h>
#include <math.h>
#include <stdio.h>

/* Helpers */

#define DEG2RAD (M_PI / 180.0)
#define RAD2DEG (180.0 / M_PI)

static inline double _f64(Value *args, int i) { return args[i].number.f64; }

static inline Value _round_op(Value *args, double (*fn)(double)) {
  Value val = args[1];
  Number *n = &val.number;
  gint64 result = (n->kind == NUM_INT64) ? n->i64 : (gint64)fn(n->f64);
  return int__init__(result, U_ONE);
}

static GRand *_rng(void) {
  static GRand *rng = NULL;
  if (G_UNLIKELY(rng == NULL))
    rng = g_rand_new();
  return rng;
}

/* Random */

static Value numerobis_builtin_random(Value *args, ...) {
  return float__init__(g_rand_double(_rng()), U_ONE);
}

static Value numerobis_builtin_randint(Value *args, ...) {
  gint64 lo = args[1].number.i64;
  gint64 hi = args[2].number.i64;
  gint64 result =
      (gint64)g_rand_int_range(_rng(), (gint32)lo, (gint32)(hi + 1));
  return int__init__(result, U_ONE);
}

/* Rounding */

static Value numerobis_builtin_floor(Value *args, ...) {
  return _round_op(args, floor);
}
static Value numerobis_builtin_ceil(Value *args, ...) {
  return _round_op(args, ceil);
}
static Value numerobis_builtin_round(Value *args, ...) {
  return _round_op(args, round);
}
static Value numerobis_builtin_trunc(Value *args, ...) {
  return _round_op(args, trunc);
}

/* Basic math */

static Value numerobis_builtin_sqrt(Value *args, ...) {
  return float__init__(sqrt(_f64(args, 1)), U_ONE);
}

static Value numerobis_builtin_cbrt(Value *args, ...) {
  return float__init__(cbrt(_f64(args, 1)), U_ONE);
}

static Value numerobis_builtin_abs(Value *args, ...) {
  return float__init__(fabs(_f64(args, 1)), U_ONE);
}

static Value numerobis_builtin_pow(Value *args, ...) {
  return float__init__(pow(_f64(args, 1), _f64(args, 2)), U_ONE);
}

static Value numerobis_builtin_exp(Value *args, ...) {
  return float__init__(exp(_f64(args, 1)), U_ONE);
}

static Value numerobis_builtin_exp2(Value *args, ...) {
  return float__init__(exp2(_f64(args, 1)), U_ONE);
}

static Value numerobis_builtin_hypot(Value *args, ...) {
  return float__init__(hypot(_f64(args, 1), _f64(args, 2)), U_ONE);
}

static Value numerobis_builtin_sign(Value *args, ...) {
  double v = _f64(args, 1);
  double s = (v > 0.0) - (v < 0.0); /* -1, 0, or 1 */
  return float__init__(s, U_ONE);
}

static Value numerobis_builtin_clamp(Value *args, ...) {
  double v = _f64(args, 1);
  double lo = _f64(args, 2);
  double hi = _f64(args, 3);
  return float__init__(v < lo ? lo : (v > hi ? hi : v), U_ONE);
}

static Value numerobis_builtin_min(Value *args, ...) {
  return float__init__(fmin(_f64(args, 1), _f64(args, 2)), U_ONE);
}

static Value numerobis_builtin_max(Value *args, ...) {
  return float__init__(fmax(_f64(args, 1), _f64(args, 2)), U_ONE);
}

/* Logarithms */

static Value numerobis_builtin_log(Value *args, ...) {
  return float__init__(log(_f64(args, 1)), U_ONE);
}

static Value numerobis_builtin_log2(Value *args, ...) {
  return float__init__(log2(_f64(args, 1)), U_ONE);
}

static Value numerobis_builtin_log10(Value *args, ...) {
  return float__init__(log10(_f64(args, 1)), U_ONE);
}

static Value numerobis_builtin_log1p(Value *args, ...) {
  return float__init__(log1p(_f64(args, 1)), U_ONE);
}

static Value numerobis_builtin_logn(Value *args, ...) {
  /* log_base(x) = log(x) / log(base) */
  return float__init__(log(_f64(args, 1)) / log(_f64(args, 2)), U_ONE);
}

/* Trigonometry (radians) */

static Value numerobis_builtin_sin(Value *args, ...) {
  return float__init__(sin(_f64(args, 1)), U_ONE);
}
static Value numerobis_builtin_cos(Value *args, ...) {
  return float__init__(cos(_f64(args, 1)), U_ONE);
}
static Value numerobis_builtin_tan(Value *args, ...) {
  return float__init__(tan(_f64(args, 1)), U_ONE);
}
static Value numerobis_builtin_asin(Value *args, ...) {
  return float__init__(asin(_f64(args, 1)), U_ONE);
}
static Value numerobis_builtin_acos(Value *args, ...) {
  return float__init__(acos(_f64(args, 1)), U_ONE);
}
static Value numerobis_builtin_atan(Value *args, ...) {
  return float__init__(atan(_f64(args, 1)), U_ONE);
}
static Value numerobis_builtin_atan2(Value *args, ...) {
  return float__init__(atan2(_f64(args, 1), _f64(args, 2)), U_ONE);
}

/* Trigonometry (degrees) */

static Value numerobis_builtin_sind(Value *args, ...) {
  return float__init__(sin(_f64(args, 1) * DEG2RAD), U_ONE);
}
static Value numerobis_builtin_cosd(Value *args, ...) {
  return float__init__(cos(_f64(args, 1) * DEG2RAD), U_ONE);
}
static Value numerobis_builtin_tand(Value *args, ...) {
  return float__init__(tan(_f64(args, 1) * DEG2RAD), U_ONE);
}
static Value numerobis_builtin_asind(Value *args, ...) {
  return float__init__(asin(_f64(args, 1)) * RAD2DEG, U_ONE);
}
static Value numerobis_builtin_acosd(Value *args, ...) {
  return float__init__(acos(_f64(args, 1)) * RAD2DEG, U_ONE);
}
static Value numerobis_builtin_atand(Value *args, ...) {
  return float__init__(atan(_f64(args, 1)) * RAD2DEG, U_ONE);
}

static Value numerobis_builtin_atan2d(Value *args, ...) {
  return float__init__(atan2(_f64(args, 1), _f64(args, 2)) * RAD2DEG, U_ONE);
}

/* Hyperbolic */

static Value numerobis_builtin_sinh(Value *args, ...) {
  return float__init__(sinh(_f64(args, 1)), U_ONE);
}
static Value numerobis_builtin_cosh(Value *args, ...) {
  return float__init__(cosh(_f64(args, 1)), U_ONE);
}
static Value numerobis_builtin_tanh(Value *args, ...) {
  return float__init__(tanh(_f64(args, 1)), U_ONE);
}
static Value numerobis_builtin_asinh(Value *args, ...) {
  return float__init__(asinh(_f64(args, 1)), U_ONE);
}
static Value numerobis_builtin_acosh(Value *args, ...) {
  return float__init__(acosh(_f64(args, 1)), U_ONE);
}
static Value numerobis_builtin_atanh(Value *args, ...) {
  return float__init__(atanh(_f64(args, 1)), U_ONE);
}

/* Angle conversion */

static Value numerobis_builtin_deg_to_rad(Value *args, ...) {
  return float__init__(_f64(args, 1) * DEG2RAD, U_ONE);
}

static Value numerobis_builtin_rad_to_deg(Value *args, ...) {
  return float__init__(_f64(args, 1) * RAD2DEG, U_ONE);
}

/* Registration */

void numerobis_math_register_builtins(void) {
  /* Random */
  u_extern_register("random", numerobis_builtin_random);
  u_extern_register("randint", numerobis_builtin_randint);

  /* Rounding */
  u_extern_register("floor", numerobis_builtin_floor);
  u_extern_register("ceil", numerobis_builtin_ceil);
  u_extern_register("round", numerobis_builtin_round);
  u_extern_register("trunc", numerobis_builtin_trunc);

  /* Basic math */
  u_extern_register("sqrt", numerobis_builtin_sqrt);
  u_extern_register("cbrt", numerobis_builtin_cbrt);
  u_extern_register("abs", numerobis_builtin_abs);
  u_extern_register("pow", numerobis_builtin_pow);
  u_extern_register("exp", numerobis_builtin_exp);
  u_extern_register("exp2", numerobis_builtin_exp2);
  u_extern_register("hypot", numerobis_builtin_hypot);
  u_extern_register("sign", numerobis_builtin_sign);
  u_extern_register("clamp", numerobis_builtin_clamp);
  u_extern_register("min", numerobis_builtin_min);
  u_extern_register("max", numerobis_builtin_max);

  /* Logarithms */
  u_extern_register("log", numerobis_builtin_log);
  u_extern_register("log2", numerobis_builtin_log2);
  u_extern_register("log10", numerobis_builtin_log10);
  u_extern_register("log1p", numerobis_builtin_log1p);
  u_extern_register("logn", numerobis_builtin_logn);

  /* Trigonometry (radians) */
  u_extern_register("sin", numerobis_builtin_sin);
  u_extern_register("cos", numerobis_builtin_cos);
  u_extern_register("tan", numerobis_builtin_tan);
  u_extern_register("asin", numerobis_builtin_asin);
  u_extern_register("acos", numerobis_builtin_acos);
  u_extern_register("atan", numerobis_builtin_atan);
  u_extern_register("atan2", numerobis_builtin_atan2);

  /* Trigonometry (degrees) */
  u_extern_register("sind", numerobis_builtin_sind);
  u_extern_register("cosd", numerobis_builtin_cosd);
  u_extern_register("tand", numerobis_builtin_tand);
  u_extern_register("asind", numerobis_builtin_asind);
  u_extern_register("acosd", numerobis_builtin_acosd);
  u_extern_register("atand", numerobis_builtin_atand);
  u_extern_register("atan2d", numerobis_builtin_atan2d);

  /* Hyperbolic */
  u_extern_register("sinh", numerobis_builtin_sinh);
  u_extern_register("cosh", numerobis_builtin_cosh);
  u_extern_register("tanh", numerobis_builtin_tanh);
  u_extern_register("asinh", numerobis_builtin_asinh);
  u_extern_register("acosh", numerobis_builtin_acosh);
  u_extern_register("atanh", numerobis_builtin_atanh);

  /* Angle conversion */
  u_extern_register("deg_to_rad", numerobis_builtin_deg_to_rad);
  u_extern_register("rad_to_deg", numerobis_builtin_rad_to_deg);
}
