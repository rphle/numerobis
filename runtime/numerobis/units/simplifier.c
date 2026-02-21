#include "simplifier.h"
#include "units.h"
#include <glib.h>
#include <math.h>
#include <stdbool.h>
#include <stddef.h>

static UnitNode *do_simplify(UnitNode *node);
static UnitNode *simplify_neg(UnitNode *node);
static UnitNode *simplify_power(UnitNode *node);
static UnitNode *simplify_product(UnitNode *node);
static UnitNode *simplify_sum(UnitNode *node);

static bool unit_equal(UnitNode *a, UnitNode *b) {
  if (a == b)
    return true;
  if (!a || !b)
    return false;
  if (a->kind != b->kind)
    return false;

  switch (a->kind) {
  case UNIT_ONE:
    return true;

  case UNIT_SCALAR:
    return a->as.scalar.value == b->as.scalar.value;

  case UNIT_IDENTIFIER:
    return a->as.label.id == b->as.label.id;

  case UNIT_NEG:
  case UNIT_EXPRESSION:
    return unit_equal(a->as.unary.value, b->as.unary.value);

  case UNIT_POWER:
    return unit_equal(a->as.power.base, b->as.power.base) &&
           unit_equal(a->as.power.exponent, b->as.power.exponent);

  case UNIT_PRODUCT:
  case UNIT_SUM: {
    // O(n^2) matching for order-insensitive equality
    GPtrArray *av = a->as.group.values;
    GPtrArray *bv = b->as.group.values;
    if (av->len != bv->len)
      return false;

    // which elements of b have already been matched?
    bool *matched = g_new0(bool, bv->len);

    for (guint i = 0; i < av->len; i++) {
      bool found = false;
      for (guint j = 0; j < bv->len; j++) {
        if (!matched[j] &&
            unit_equal(g_ptr_array_index(av, i), g_ptr_array_index(bv, j))) {
          matched[j] = true;
          found = true;
          break;
        }
      }
      if (!found) {
        g_free(matched);
        return false;
      }
    }
    g_free(matched);
    return true;
  }
  }
  return false;
}

static GPtrArray *flatten(GPtrArray *values, UnitKind kind) {
  GPtrArray *flat = g_ptr_array_new();

  for (guint i = 0; i < values->len; i++) {
    UnitNode *child = do_simplify(g_ptr_array_index(values, i));

    if (child->kind == kind) {
      GPtrArray *cv = child->as.group.values;
      for (guint j = 0; j < cv->len; j++)
        g_ptr_array_add(flat, g_ptr_array_index(cv, j));
    } else if (child->kind != UNIT_ONE) {
      g_ptr_array_add(flat, child);
    }
  }
  return flat;
}

static UnitNode *finalize(GPtrArray *values, UnitKind kind, double identity) {
  if (values->len == 0)
    return U_NUM(identity);

  if (values->len == 1)
    return g_ptr_array_index(values, 0);

  UnitNode *node = (kind == UNIT_PRODUCT) ? unit_product_new() : unit_sum_new();
  for (guint i = 0; i < values->len; i++)
    g_ptr_array_add(node->as.group.values, g_ptr_array_index(values, i));
  return node;
}

typedef struct {
  double coeff;
  UnitNode *base;
} Decomposed;

static Decomposed decompose(UnitNode *node) {
  if (node->kind != UNIT_PRODUCT)
    return (Decomposed){1.0, node};

  GPtrArray *vals = node->as.group.values;
  double coeff = 1.0;
  bool had_scalar = false;
  GPtrArray *others = g_ptr_array_new();

  for (guint i = 0; i < vals->len; i++) {
    UnitNode *v = g_ptr_array_index(vals, i);
    if (v->kind == UNIT_SCALAR) {
      coeff *= v->as.scalar.value;
      had_scalar = true;
    } else {
      g_ptr_array_add(others, v);
    }
  }

  if (!had_scalar) {
    return (Decomposed){1.0, node};
  }

  UnitNode *base;
  if (others->len == 0) {
    base = unit_one_new();
  } else if (others->len == 1) {
    base = g_ptr_array_index(others, 0);
  } else {
    base = unit_product_new();
    for (guint i = 0; i < others->len; i++)
      g_ptr_array_add(base->as.group.values, g_ptr_array_index(others, i));
  }
  return (Decomposed){coeff, base};
}

// dispatch
static UnitNode *do_simplify(UnitNode *node) {
  if (!node)
    return unit_one_new();

  switch (node->kind) {
  case UNIT_EXPRESSION:
    return do_simplify(node->as.unary.value);

  case UNIT_NEG:
    return simplify_neg(node);

  case UNIT_POWER:
    return simplify_power(node);

  case UNIT_PRODUCT:
    return simplify_product(node);

  case UNIT_SUM:
    return simplify_sum(node);

  default:
    return node;
  }
}

static UnitNode *simplify_neg(UnitNode *node) {
  UnitNode *val = do_simplify(node->as.unary.value);

  if (val->kind == UNIT_ONE)
    return U_NUM(-1.0);

  if (val->kind == UNIT_SCALAR)
    return U_NUM(-val->as.scalar.value);

  return unit_neg_new(val);
}

static UnitNode *simplify_power(UnitNode *node) {
  UnitNode *base = do_simplify(node->as.power.base);
  UnitNode *exp = do_simplify(node->as.power.exponent);

  if (exp->kind == UNIT_SCALAR) {
    if (exp->as.scalar.value == 0.0)
      return U_NUM(1.0);
    if (exp->as.scalar.value == 1.0)
      return base;
  }

  if (exp->kind == UNIT_ONE)
    return base;

  if (base->kind == UNIT_ONE)
    return U_NUM(1.0);

  // scalar^scalar
  if (base->kind == UNIT_SCALAR && exp->kind == UNIT_SCALAR)
    return U_NUM(pow(base->as.scalar.value, exp->as.scalar.value));

  // (x^a)^b  ->  x^(simplify(a * b))
  if (base->kind == UNIT_POWER) {
    UnitNode *combined_exp = unit_product_new();
    g_ptr_array_add(combined_exp->as.group.values, base->as.power.exponent);
    g_ptr_array_add(combined_exp->as.group.values, exp);
    UnitNode *new_exp = simplify_product(combined_exp);
    // Recurse to allow further reductions on the new power node.
    return simplify_power(unit_power_new(base->as.power.base, new_exp));
  }

  // (a * b * ...)^n  ->  a^n * b^n * ...
  if (base->kind == UNIT_PRODUCT) {
    UnitNode *prod = unit_product_new();
    GPtrArray *bv = base->as.group.values;
    for (guint i = 0; i < bv->len; i++) {
      UnitNode *factor = g_ptr_array_index(bv, i);
      g_ptr_array_add(prod->as.group.values, unit_power_new(factor, exp));
    }
    return simplify_product(prod);
  }

  return unit_power_new(base, exp);
}

static UnitNode *simplify_product(UnitNode *node) {
  GPtrArray *terms = flatten(node->as.group.values, UNIT_PRODUCT);

  double scalar_acc = 1.0;

  // bases[i] has accumulated exponents exps[i]
  GPtrArray *bases = g_ptr_array_new();
  GPtrArray *exps = g_ptr_array_new();

  for (guint i = 0; i < terms->len; i++) {
    UnitNode *term = g_ptr_array_index(terms, i);

    if (term->kind == UNIT_SCALAR) {
      scalar_acc *= term->as.scalar.value;
      continue;
    }

    UnitNode *base;
    UnitNode *exp_node;

    if (term->kind == UNIT_POWER) {
      base = term->as.power.base;
      exp_node = term->as.power.exponent;
    } else {
      base = term;
      exp_node = U_NUM(1.0);
    }

    // find or create group for this base
    int idx = -1;
    for (guint j = 0; j < bases->len; j++) {
      if (unit_equal(g_ptr_array_index(bases, j), base)) {
        idx = (int)j;
        break;
      }
    }

    if (idx < 0) {
      GPtrArray *eg = g_ptr_array_new();
      g_ptr_array_add(eg, exp_node);
      g_ptr_array_add(bases, base);
      g_ptr_array_add(exps, eg);
    } else {
      g_ptr_array_add(g_ptr_array_index(exps, (guint)idx), exp_node);
    }
  }

  // reconstruct result
  GPtrArray *new_values = g_ptr_array_new();

  if (scalar_acc != 1.0)
    g_ptr_array_add(new_values, U_NUM(scalar_acc));

  for (guint i = 0; i < bases->len; i++) {
    UnitNode *base = g_ptr_array_index(bases, i);
    GPtrArray *eg = g_ptr_array_index(exps, i);

    UnitNode *total_exp;
    if (eg->len == 1) {
      total_exp = g_ptr_array_index(eg, 0);
    } else {
      // sum the exponents and simplify
      UnitNode *sum_node = unit_sum_new();
      for (guint j = 0; j < eg->len; j++)
        g_ptr_array_add(sum_node->as.group.values, g_ptr_array_index(eg, j));
      total_exp = simplify_sum(sum_node);
    }

    if (total_exp->kind == UNIT_SCALAR) {
      if (total_exp->as.scalar.value == 0.0)
        continue;
      if (total_exp->as.scalar.value == 1.0) {
        g_ptr_array_add(new_values, base);
        continue;
      }
    }

    g_ptr_array_add(new_values, unit_power_new(base, total_exp));
  }

  return finalize(new_values, UNIT_PRODUCT, 1.0);
}

static UnitNode *simplify_sum(UnitNode *node) {
  GPtrArray *terms = flatten(node->as.group.values, UNIT_SUM);

  double scalar_acc = 0.0;

  GPtrArray *bases = g_ptr_array_new();
  GArray *coeffs = g_array_new(FALSE, FALSE, sizeof(double));

  for (guint i = 0; i < terms->len; i++) {
    UnitNode *term = g_ptr_array_index(terms, i);

    if (term->kind == UNIT_SCALAR) {
      scalar_acc += term->as.scalar.value;
      continue;
    }

    Decomposed d = decompose(term);

    if (d.base->kind == UNIT_ONE) {
      scalar_acc += d.coeff;
      continue;
    }

    int idx = -1;
    for (guint j = 0; j < bases->len; j++) {
      if (unit_equal(g_ptr_array_index(bases, j), d.base)) {
        idx = (int)j;
        break;
      }
    }

    if (idx < 0) {
      g_ptr_array_add(bases, d.base);
      g_array_append_val(coeffs, d.coeff);
    } else {
      double *c = &g_array_index(coeffs, double, (guint)idx);
      *c += d.coeff;
    }
  }

  GPtrArray *new_values = g_ptr_array_new();

  if (scalar_acc != 0.0)
    g_ptr_array_add(new_values, U_NUM(scalar_acc));

  for (guint i = 0; i < bases->len; i++) {
    UnitNode *base = g_ptr_array_index(bases, i);
    double total_coeff = g_array_index(coeffs, double, i);

    if (total_coeff == 0.0)
      continue;

    if (total_coeff == 1.0) {
      g_ptr_array_add(new_values, base);
      continue;
    }

    UnitNode *prod = unit_product_new();
    g_ptr_array_add(prod->as.group.values, U_NUM(total_coeff));

    if (base->kind == UNIT_PRODUCT) {
      GPtrArray *bv = base->as.group.values;
      for (guint j = 0; j < bv->len; j++)
        g_ptr_array_add(prod->as.group.values, g_ptr_array_index(bv, j));
    } else {
      g_ptr_array_add(prod->as.group.values, base);
    }

    g_ptr_array_add(new_values, prod);
  }

  return finalize(new_values, UNIT_SUM, 0.0);
}

UnitNode *unit_simplify(UnitNode *node) {
  if (!node)
    return unit_one_new();
  return do_simplify(node);
}
