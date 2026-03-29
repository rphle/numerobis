#ifndef NUMEROBIS_LIST_H
#define NUMEROBIS_LIST_H

#include "../units/units.h"
#include "../values.h"
#include "number.h"

#include <glib.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>

Value list__init__(GArray *x);

Value list_of(Value first, ...);

static inline size_t _list_len(const GArray *self) {
  return self ? self->len : 0;
}

static inline Value list_len(Value self) {
  return int__init__((gint64)_list_len(self.list), U_ONE);
}

Value list_append(Value self, Value val);
Value list_extend(Value self, Value other);
Value list_insert(Value self, Value index, Value val);
Value list_pop(Value self, Value index);

void list_methods_init(void);

#endif
