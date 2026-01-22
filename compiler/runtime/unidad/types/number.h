#ifndef UNIDAD_NUMBER_H
#define UNIDAD_NUMBER_H

#include "../values.h"
#include <glib.h>
#include <stdbool.h>

Value *int__init__(gint64 x, UnitNode *unit);
Value *float__init__(gdouble x, UnitNode *unit);

Value *number__convert__(Value *self, UnitNode *target);

typedef enum {
  OP_ADD,
  OP_SUB,
  OP_MUL,
  OP_DIV,
  OP_POW,
  OP_MOD
} OpKind;

#endif
