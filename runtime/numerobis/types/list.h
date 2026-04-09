#ifndef NUMEROBIS_LIST_H
#define NUMEROBIS_LIST_H

#include "../libs/gc_stb_ds.h"
#include "../units/units.h"
#include "../values.h"
#include "number.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>

Value list__init__(Value *items);

Value list_of(const Value *items, size_t len);

static inline size_t _list_len(const List *self) {
  return (self && self->items) ? arrlen(self->items) : 0;
}

static inline Value list_len(Value self) {
  long len = (long)_list_len(self.list);
  return int__init__(len, U_ONE);
}

void list_methods_init(void);

void numerobis_list_register_externs(void);

#endif
