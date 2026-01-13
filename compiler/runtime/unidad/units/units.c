#include "units.h"
#include <stdarg.h>

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

UnitNode *unit_id_new(const char *name) {
  UnitNode *node = unit_node_alloc(UNIT_IDENTIFIER);
  node->as.label.name = g_strdup(name);
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
