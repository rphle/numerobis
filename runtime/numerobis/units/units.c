#include "units.h"
#include "simplifier.h"
#include <glib.h>
#include <stdarg.h>
#include <stdint.h>

static UnitNode *unit_node_alloc(UnitKind kind) {
  UnitNode *node = g_malloc(sizeof(UnitNode));
  node->kind = kind;
  return node;
}

UnitNode *unit_scalar_new(double value, UnitNode *unit) {
  UnitNode *node = unit_node_alloc(UNIT_SCALAR);
  node->as.scalar.value = value;
  return node;
}

UnitNode *unit_id_new(const char *name, uint16_t id) {
  UnitNode *node = unit_node_alloc(UNIT_IDENTIFIER);
  node->as.label.name = g_strdup(name);
  node->as.label.id = id;
  return node;
}

UnitNode *unit_product_new() {
  UnitNode *node = unit_node_alloc(UNIT_PRODUCT);
  node->as.group.values = g_ptr_array_new();
  return node;
}

UnitNode *unit_sum_new() {
  UnitNode *node = unit_node_alloc(UNIT_SUM);
  node->as.group.values = g_ptr_array_new();
  return node;
}

UnitNode *unit_expression_new(UnitNode *value) {
  UnitNode *node = unit_node_alloc(UNIT_EXPRESSION);
  node->as.unary.value = value;
  return node;
}

UnitNode *unit_neg_new(UnitNode *value) {
  UnitNode *node = unit_node_alloc(UNIT_NEG);
  node->as.unary.value = value;
  return node;
}

UnitNode *unit_power_new(UnitNode *base, UnitNode *exponent) {
  UnitNode *node = unit_node_alloc(UNIT_POWER);
  node->as.power.base = base;
  node->as.power.exponent = exponent;
  return node;
}

UnitNode *unit_one_new() { return unit_node_alloc(UNIT_ONE); }

// helpers

UnitNode *unit_product_of(UnitNode *first, ...) {
  UnitNode *node = unit_product_new();
  va_list args;
  va_start(args, first);
  for (UnitNode *curr = first; curr != NULL; curr = va_arg(args, UnitNode *)) {
    g_ptr_array_add(node->as.group.values, curr);
  }
  va_end(args);
  return node;
}

UnitNode *unit_sum_of(UnitNode *first, ...) {
  UnitNode *node = unit_sum_new();
  va_list args;
  va_start(args, first);
  for (UnitNode *curr = first; curr != NULL; curr = va_arg(args, UnitNode *)) {
    g_ptr_array_add(node->as.group.values, curr);
  }
  va_end(args);
  return node;
}

static bool is_compound(UnitNode *node) {
  if (node == NULL)
    return false;
  return (node->kind == UNIT_SUM || node->kind == UNIT_PRODUCT ||
          node->kind == UNIT_NEG || node->kind == UNIT_POWER);
}

static void print_unit_rec(UnitNode *node, GString *out, bool in_denominator) {
  if (node == NULL)
    return;

  switch (node->kind) {
  case UNIT_ONE:
    break;
  case UNIT_SCALAR: {
    double val = node->as.scalar.value;
    if (val == (long)val)
      g_string_append_printf(out, "%ld", (long)val);
    else
      g_string_append_printf(out, "%g", val);
    break;
  }

  case UNIT_IDENTIFIER:
    if (node->as.label.name) {
      g_string_append(out, node->as.label.name);
    }
    break;

  case UNIT_PRODUCT: {
    GPtrArray *values = node->as.group.values;
    GPtrArray *num = g_ptr_array_new();
    GPtrArray *denom = g_ptr_array_new();

    for (guint i = 0; i < values->len; i++) {
      UnitNode *child = g_ptr_array_index(values, i);

      bool is_denom = false;

      if (child->kind == UNIT_POWER) {
        UnitNode *exp = child->as.power.exponent;
        if (exp->kind == UNIT_SCALAR && exp->as.scalar.value < 0) {
          is_denom = true;
        } else if (exp->kind == UNIT_NEG) {
          is_denom = true;
        }
      } else if (child->kind == UNIT_ONE) {
        continue;
      }

      if (is_denom)
        g_ptr_array_add(denom, child);
      else
        g_ptr_array_add(num, child);
    }

    if (num->len == 0) {
      // If everything is in denominator (e.g. s^-1), numerator is 1
      g_string_append(out, "1");
    } else {
      for (guint i = 0; i < num->len; i++) {
        if (i > 0)
          g_string_append(out, "*");
        UnitNode *child = g_ptr_array_index(num, i);
        bool needs_parens = (child->kind == UNIT_SUM);
        if (needs_parens)
          g_string_append(out, "(");
        print_unit_rec(child, out, false);
        if (needs_parens)
          g_string_append(out, ")");
      }
    }

    if (denom->len > 0) {
      g_string_append(out, "/");

      bool group_denom = (denom->len > 1);
      if (group_denom)
        g_string_append(out, "(");

      for (guint i = 0; i < denom->len; i++) {
        if (i > 0)
          g_string_append(out, "*");

        UnitNode *child = g_ptr_array_index(denom, i);

        if (child->kind == UNIT_POWER) {
          UnitNode *base = child->as.power.base;
          UnitNode *exp = child->as.power.exponent;

          bool base_parens = is_compound(base);
          if (base_parens)
            g_string_append(out, "(");
          print_unit_rec(base, out, false);
          if (base_parens)
            g_string_append(out, ")");

          if (exp->kind == UNIT_SCALAR) {
            double val = -1.0 * exp->as.scalar.value;
            if (val != 1.0) {
              g_string_append(out, "^");
              if (val == (long)val)
                g_string_append_printf(out, "%ld", (long)val);
              else
                g_string_append_printf(out, "%g", val);
            }
          } else if (exp->kind == UNIT_NEG) {
            // x ^ -y  --> / x^y
            g_string_append(out, "^");
            bool exp_parens = is_compound(exp->as.unary.value);
            if (exp_parens)
              g_string_append(out, "(");
            print_unit_rec(exp->as.unary.value, out, false);
            if (exp_parens)
              g_string_append(out, ")");
          }
        }
      }
      if (group_denom)
        g_string_append(out, ")");
    }

    g_ptr_array_free(num, TRUE);
    g_ptr_array_free(denom, TRUE);
    break;
  }

  case UNIT_SUM: {
    GPtrArray *values = node->as.group.values;
    for (guint i = 0; i < values->len; i++) {
      if (i > 0)
        g_string_append(out, "+");
      UnitNode *child = g_ptr_array_index(values, i);
      print_unit_rec(child, out, false);
    }
    break;
  }

  case UNIT_EXPRESSION:
    g_string_append(out, "[");
    print_unit_rec(node->as.unary.value, out, false);
    g_string_append(out, "]");
    break;

  case UNIT_NEG: {
    g_string_append(out, "-");
    UnitNode *child = node->as.unary.value;
    bool needs_parens = is_compound(child);
    if (needs_parens)
      g_string_append(out, "(");
    print_unit_rec(child, out, false);
    if (needs_parens)
      g_string_append(out, ")");
    break;
  }

  case UNIT_POWER: {
    UnitNode *base = node->as.power.base;
    UnitNode *exp = node->as.power.exponent;

    // don't render the exponent at all when it is the scalar 1 or ONE
    if ((exp->kind == UNIT_SCALAR && exp->as.scalar.value == 1.0) ||
        exp->kind == UNIT_ONE) {
      bool base_parens = is_compound(base);
      if (base_parens)
        g_string_append(out, "(");
      print_unit_rec(base, out, false);
      if (base_parens)
        g_string_append(out, ")");
      break;
    }

    bool base_parens = is_compound(base);
    bool exp_parens =
        (exp->kind != UNIT_SCALAR && exp->kind != UNIT_IDENTIFIER);

    if (base_parens)
      g_string_append(out, "(");
    print_unit_rec(base, out, false);
    if (base_parens)
      g_string_append(out, ")");

    g_string_append(out, "^");

    if (exp_parens)
      g_string_append(out, "(");
    print_unit_rec(exp, out, false);
    if (exp_parens)
      g_string_append(out, ")");
    break;
  }
  }
}

GString *print_unit(UnitNode *node) {
  UnitNode *simplified = unit_simplify(node);
  GString *out = g_string_new("");
  print_unit_rec(simplified, out, false);
  return out;
}
