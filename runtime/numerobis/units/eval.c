#include "eval.h"
#include "../values.h"
#include "glib.h"
#include "units.h"

#include <math.h>
#include <stdbool.h>
#include <stddef.h>

gdouble eval_unit(const Unit *u, gdouble number, EvalMode mode) {
  if (u == NULL)
    return 1.0;

  if (u->len == 0 && u->scalar == 1.0)
    return 1.0;

  gdouble result = 1.0;

  for (uint16_t i = 0; i < u->len; i++) {
    uint16_t id = u->data[i].id;
    int16_t exp = u->data[i].exp;

    gdouble base_val;
    if (mode == EVAL_BASE)
      base_val = base_unit(id, number);
    else if (mode == EVAL_INVERTED)
      base_val = unit_id_eval(id, number);
    else /* EVAL_NORMAL */
      base_val = unit_id_eval_normal(id, number);

    if (base_val == 0.0)
      result = 0.0;
    else
      result *= pow(base_val, (gdouble)exp);
  }

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

gdouble eval_number(Number *n, const uint64_t *_unit_hash) {
  const Unit *u = unit_get(_unit_hash != NULL ? *_unit_hash : n->unit);
  gdouble value = n->kind == NUM_INT64 ? (gdouble)(n->i64) : n->f64;

  if (!(is_one(u) && u->scalar == 1.0)) {
    gdouble base = eval_unit(u, value, EVAL_BASE);
    gdouble target = eval_unit(u, value, EVAL_INVERTED);
    if (base == 0.0)
      return 0.0;
    gdouble res = target / base;
    value = unit_is_logarithmic(u) ? res : value * res;
  }

  return value;
}

GString *print_number(Number *n) {
  gdouble value = eval_number(n, NULL);

  GString *out = g_string_new("");
  g_string_printf(out, "%g", value);

  const Unit *u = unit_get(n->unit);
  if (is_one(u) && u->scalar == 1.0) {
    return out;
  }

  GString *unit = unit_print(u);
  size_t len = g_utf8_strlen(unit->str, unit->len);

  if (len > 0) {
    g_string_append(out, " ");
    g_string_append(out, unit->str);
  }

  g_string_free(unit, TRUE);

  return out;
}
