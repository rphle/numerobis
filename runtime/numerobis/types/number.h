#ifndef NUMEROBIS_NUMBER_H
#define NUMEROBIS_NUMBER_H

#include "../values.h"

#include <glib.h>
#include <stdbool.h>

Value int__init__(gint64 x, const uint64_t unit);
Value num__init__(gdouble x, const uint64_t unit);

Value number__convert__(Value self, const uint64_t target);

typedef enum {
  OP_ADD,
  OP_SUB,
  OP_MUL,
  OP_DIV,
  OP_POW,
  OP_MOD,
  OP_DADD,
  OP_DSUB,
} OpKind;

void number_methods_init(void);

#endif
