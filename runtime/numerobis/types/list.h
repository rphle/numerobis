#ifndef NUMEROBIS_LIST_H
#define NUMEROBIS_LIST_H

#include <glib.h>
#include <stdbool.h>
#include <stddef.h>

#include "../values.h"

Value *list__init__(GArray *x);

Value *list_of(Value *first, ...);

Value *list_append(Value *self, Value *val);
Value *list_extend(Value *self, Value *other);
Value *list_insert(Value *self, Value *index, Value *val);
Value *list_pop(Value *self, Value *index);

#endif
