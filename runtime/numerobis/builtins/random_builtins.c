#include "random_builtins.h"

#include "../extern.h"
#include "../types/number.h"
#include "../units/units.h"
#include "../utils/utils.h"
#include "../values.h"

#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <time.h>

static void rng_seed_once(void) {
  static int seeded = 0;
  if (!seeded) {
    seeded = 1;
    uintptr_t entropy = (uintptr_t)&seeded;
    srand((unsigned)(time(NULL) ^ entropy ^ (entropy >> 16)));
  }
}

static double rand_double(void) {
  rng_seed_once();
  return rand() / ((double)RAND_MAX + 1.0);
}

static long rand_int_range(long lo, long hi_exclusive) {
  rng_seed_once();
  if (hi_exclusive <= lo)
    return lo;
  long span = hi_exclusive - lo;
  return lo + (long)(rand_double() * span);
}

static double rand_double_range(double lo, double hi) {
  return lo + (hi - lo) * rand_double();
}

static Value numerobis_builtin_random(Value *args) {
  (void)args;
  return num__init__(rand_double(), U_ONE);
}

static Value numerobis_builtin_randint(Value *args) {
  long lo = _i64(args[1]);
  long hi = _i64(args[2]);
  long result = rand_int_range(lo, hi + 1);
  return int__init__(result, U_ONE);
}

static Value numerobis_builtin_uniform(Value *args) {
  double lo = _f64(args[1]);
  double hi = _f64(args[2]);
  double result = rand_double_range(lo, hi);
  return num__init__(result, U_ONE);
}

static Value numerobis_builtin_gaussian(Value *args) {
  double mean = 0.0;
  double stddev = 1.0;

  if (args[1].type != VALUE_EMPTY)
    mean = _f64(args[1]);
  if (args[2].type != VALUE_EMPTY)
    stddev = _f64(args[2]);

  double u1 = rand_double();
  double u2 = rand_double();

  if (u1 < 1e-12)
    u1 = 1e-12;

  double z0 = sqrt(-2.0 * log(u1)) * cos(2.0 * M_PI * u2);
  return num__init__(mean + stddev * z0, U_ONE);
}

void numerobis_random_register_builtins(void) {
  u_extern_register("random", numerobis_builtin_random);
  u_extern_register("randint", numerobis_builtin_randint);
  u_extern_register("uniform", numerobis_builtin_uniform);
  u_extern_register("gaussian", numerobis_builtin_gaussian);
}
