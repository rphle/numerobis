#include "eval.h"
#include "../libs/sds.h"
#include "../values.h"
#include "units.h"

#include <math.h>
#include <stdbool.h>
#include <stddef.h>

/**
 * Applies an unit function to a number.
 * * @param u The unit struct.
 * @param number The value being converted.
 * @param mode EVAsL_BASE (to base units), EVAL_INVERTED (from base to target)
 * @return The final double result.
 */
double eval_unit(const Unit *u, double number, EvalMode mode) {
  // Dimensionless checks.
  if (u == NULL || (u->len == 0 && u->scalar == 1.0)) {
    return number;
  }

  double result = 1.0;

  // Iterate over every individual factor
  for (uint16_t i = 0; i < u->len; i++) {
    uint16_t id = u->data[i].id;
    int16_t exp = u->data[i].exp;

    double base_val;

    // Fetch the transformation value for this specific dimension based on the
    // mode.
    if (mode == EVAL_BASE)
      base_val = base_unit(id, number);
    else if (mode == EVAL_INVERTED)
      base_val = unit_id_eval(id, number);
    else /* EVAL_NORMAL */
      base_val = unit_id_eval_normal(id, number);

    // Safeguard against multiplying by zero.
    if (base_val == 0.0)
      result = 0.0;
    else
      // Apply the exponent
      result *= pow(base_val, (double)exp);
  }

  // Finally, apply the overall scalar of the unit, but ONLY if we are moving
  // towards the base unit representation.
  if (mode == EVAL_BASE)
    result *= u->scalar;

  return result;
}

bool unit_is_logarithmic(const Unit *u) {
  if (is_one(u))
    return false;

  for (uint16_t i = 0; i < u->len; i++) {
    if (is_logarithmic(u->data[i].id))
      return true;
  }
  return false;
}

/* Evaluates a number with an optional unit hash, returning the value in its
 * representation unit. */
double eval_number(Number *n, const uint64_t *_unit_hash) {
  const Unit *u = unit_get(_unit_hash != NULL ? *_unit_hash : n->unit);
  double value = n->kind == NUM_INT64 ? (double)(n->i64) : n->f64;

  if (!(is_one(u) && u->scalar == 1.0)) {
    double base = eval_unit(u, value, EVAL_BASE);
    double inverted = eval_unit(u, value, EVAL_INVERTED);
    if (base == 0.0)
      return 0.0;
    double res = inverted / base;
    value = unit_is_logarithmic(u) ? res : value * res;
  }

  return value;
}

sds print_number(Number *n) {
  double value = eval_number(n, NULL);

  sds out = sdscatprintf(sdsempty(), "%g", value);

  const Unit *u = unit_get(n->unit);
  if (is_one(u) && u->scalar == 1.0) {
    return out;
  }

  sds unit_s = unit_print(u);
  if (sdslen(unit_s) > 0) {
    out = sdscat(out, " ");
    out = sdscatlen(out, unit_s, sdslen(unit_s));
  }

  sdsfree(unit_s);

  return out;
}
