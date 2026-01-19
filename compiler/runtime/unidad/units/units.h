#ifndef UNIDAD_UNITS_H
#define UNIDAD_UNITS_H

#include <glib.h>
#include <math.h>
#include <stdbool.h>
#include <stdint.h>

typedef enum {
  UNIT_SCALAR,
  UNIT_PRODUCT,
  UNIT_SUM,
  UNIT_EXPRESSION,
  UNIT_NEG,
  UNIT_POWER,
  UNIT_IDENTIFIER,
  UNIT_ONE
} UnitKind;

typedef struct UnitNode UnitNode;

struct UnitNode {
  UnitKind kind;
  union {
    struct {
      gdouble value;
    } scalar;

    struct {
      GPtrArray *values;
    } group;

    struct {
      UnitNode *value;
    } unary;

    struct {
      char *name;
      uint16_t id;
    } label;

    struct {
      UnitNode *base;
      UnitNode *exponent;
    } power;
  } as;
};

UnitNode *unit_scalar_new(double value, UnitNode *unit);
UnitNode *unit_id_new(const char *name, uint16_t id);
UnitNode *unit_product_new();
UnitNode *unit_sum_new();
UnitNode *unit_expression_new(UnitNode *value);
UnitNode *unit_neg_new(UnitNode *value);
UnitNode *unit_power_new(UnitNode *base, UnitNode *exponent);
UnitNode *unit_one_new();

UnitNode *unit_product_of(UnitNode *first, ...);
UnitNode *unit_sum_of(UnitNode *first, ...);

GString *print_unit(UnitNode *node);

#define U_PROD(...) unit_product_of(__VA_ARGS__, NULL)
#define U_SUM(...) unit_sum_of(__VA_ARGS__, NULL)
#define U_NUM(v) unit_scalar_new((v), NULL)
#define U_NUM_U(v, u) unit_scalar_new((v), (u))
#define U_ID(n, id) unit_id_new(n, id)
#define U_EXPR(v) unit_expression_new(v)
#define U_NEG(v) unit_neg_new(v)
#define U_PWR(b, e) unit_power_new((b), (e))
#define U_ONE unit_one_new()

#endif
