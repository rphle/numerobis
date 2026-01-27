#include "eval.h"
#include "../units/units.h"
#include "../values.h"
#include "glib.h"
#include "units.h"
#include <math.h>
#include <stdbool.h>
#include <stddef.h>

gdouble eval_unit(UnitNode *node, gdouble number, EvalMode mode) {
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
        result += eval_unit(child, number, mode);
      else
        result *= eval_unit(child, number, mode);
    }

    return result;
  }
  case UNIT_EXPRESSION:
    return eval_unit(node->as.unary.value, number, mode);
  case UNIT_NEG:
    return -eval_unit(node->as.unary.value, number, mode);
  case UNIT_POWER:
    return pow(eval_unit(node->as.power.base, number, mode),
               eval_unit(node->as.power.exponent, number, mode));
  case UNIT_ONE:
    return number;
  case UNIT_IDENTIFIER:
    if (mode == EVAL_BASE)
      return base_unit(node->as.label.id, number);
    else if (mode == EVAL_INVERTED) {
      return unit_id_eval(node->as.label.id, number);
    } else if (mode == EVAL_NORMAL) {
      return unit_id_eval_normal(node->as.label.id, number);
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

gdouble eval_number(Number *n, UnitNode *_unit) {
  UnitNode *unit = _unit == NULL ? n->unit : _unit;
  gdouble value = n->kind == NUM_INT64 ? (gdouble)(n->i64) : n->f64;

  if (unit->kind != UNIT_ONE) {
    gdouble base = eval_unit(unit, value, EVAL_BASE);
    gdouble target = eval_unit(unit, value, EVAL_INVERTED);

    gdouble res = target / base;
    value = is_unit_logarithmic(unit) ? res : value * res;
  }

  return value;
}

GString *print_number(Number *n) {
  gdouble value = eval_number(n, NULL);

  GString *out = g_string_new("");
  g_string_printf(out, "%g", value);

  GString *unit = print_unit(n->unit);
  size_t len = g_utf8_strlen(unit->str, unit->len);

  if (len > 0) {
    g_string_append(out, " ");
    g_string_append(out, unit->str);
  }

  return out;
}
