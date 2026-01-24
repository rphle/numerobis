#include "eval.h"
#include "../units/units.h"
#include "../values.h"
#include "glib.h"
#include "simplifier.h"
#include "units.h"
#include <math.h>
#include <stdbool.h>

gdouble eval_unit(UnitNode *node, gdouble number, bool is_base) {
  if (node == NULL)
    return 1;

  switch (node->kind) {
  case UNIT_SCALAR:
    return node->as.scalar.value;
  case UNIT_SUM:
  case UNIT_PRODUCT: {
    GPtrArray *values = node->as.group.values;
    gdouble result = node->kind == UNIT_SUM ? 0.0 : 1.0;

    for (guint i = 0; i < values->len; i++) {
      UnitNode *child = g_ptr_array_index(values, i);
      if (node->kind == UNIT_SUM)
        result += eval_unit(child, number, is_base);
      else
        result *= eval_unit(child, number, is_base);
    }

    return result;
  }
  case UNIT_EXPRESSION:
    return eval_unit(node->as.unary.value, number, is_base);
  case UNIT_NEG:
    return -eval_unit(node->as.unary.value, number, is_base);
  case UNIT_POWER:
    return pow(eval_unit(node->as.power.base, number, is_base),
               eval_unit(node->as.power.exponent, number, is_base));
  case UNIT_ONE:
    return number;
  case UNIT_IDENTIFIER:
    if (is_base)
      return base_unit(node->as.label.id, number);
    else {
      return unit_id_eval(node->as.label.id, number);
    }
  }
}

bool is_unit_logarithmic(UnitNode *node) {
  if (node == NULL)
    return 1;

  switch (node->kind) {
  case UNIT_SCALAR:
    return false;
  case UNIT_SUM:
  case UNIT_PRODUCT: {
    GPtrArray *values = node->as.group.values;
    for (guint i = 0; i < values->len; i++) {
      UnitNode *child = g_ptr_array_index(values, i);
      if (is_unit_logarithmic(child))
        return true;
    }
    return false;
  }
  case UNIT_NEG:
  case UNIT_EXPRESSION:
    return is_unit_logarithmic(node->as.unary.value);
  case UNIT_POWER:
    return is_unit_logarithmic(node->as.power.base) ||
           is_unit_logarithmic(node->as.power.exponent);
  case UNIT_ONE:
    return false;
  case UNIT_IDENTIFIER:
    return is_logarithmic(node->as.label.id);
  }
}

GString *print_number(Number *n) {
  gdouble value;
  switch (n->kind) {
  case NUM_INT64:
    value = (gdouble)(n->i64);
    break;
  case NUM_DOUBLE:
    value = n->f64;
    break;
  }

  gdouble base = eval_unit(n->unit, value, true);
  gdouble target = eval_unit(n->unit, value, false);

  gdouble res = target / base;

  if (!is_unit_logarithmic(n->unit)) {
    res = value * res;
  }

  GString *out = g_string_new("");
  g_string_printf(out, "%g %s", res, print_unit(n->unit)->str);

  return out;
}
