#include "random_builtins.h"

#include "../extern.h"
#include "../types/number.h"
#include "../units/units.h"
#include "../values.h"

#include <glib.h>
#include <math.h>
#include <stdio.h>

static GRand *_rng(void) {
  static GRand *rng = NULL;
  if (G_UNLIKELY(rng == NULL))
    rng = g_rand_new();
  return rng;
}

static Value numerobis_builtin_random(Value *args) {
  return num__init__(g_rand_double(_rng()), U_ONE);
}

static Value numerobis_builtin_randint(Value *args) {
  gint64 lo = args[1].number.i64;
  gint64 hi = args[2].number.i64;
  gint64 result =
      (gint64)g_rand_int_range(_rng(), (gint32)lo, (gint32)(hi + 1));
  return int__init__(result, U_ONE);
}

static Value numerobis_builtin_uniform(Value *args) {
  double lo = args[1].number.f64;
  double hi = args[2].number.f64;
  double result = g_rand_double_range(_rng(), lo, hi);
  return num__init__(result, U_ONE);
}

static Value numerobis_builtin_gaussian(Value *args) {
  double mean = 0.0;
  double stddev = 1.0;

  if (args[1].type != VALUE_NONE)
    mean = args[1].number.f64;
  if (args[2].type != VALUE_NONE)
    stddev = args[2].number.f64;

  double u1 = g_rand_double(_rng());
  double u2 = g_rand_double(_rng());

  if (G_UNLIKELY(u1 <= 0.0))
    u1 = 1e-12;

  double z0 = sqrt(-2.0 * log(u1)) * cos(2.0 * G_PI * u2);
  return num__init__(mean + stddev * z0, U_ONE);
}

void numerobis_random_register_builtins(void) {
  u_extern_register("random", numerobis_builtin_random);
  u_extern_register("randint", numerobis_builtin_randint);
  u_extern_register("uniform", numerobis_builtin_uniform);
  u_extern_register("gaussian", numerobis_builtin_gaussian);
}
