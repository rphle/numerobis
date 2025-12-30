#ifndef UNIDAD_STR_H
#define UNIDAD_STR_H

#include "../values.h"
#include <glib.h>
#include <stdbool.h>
#include <stddef.h>

Value *str__init__(GString *x);

size_t str_len(const GString *self);

bool str__bool__(GString *self);

GString *str__add__(GString *self, GString *other);
GString *str__mul__(GString *self, ssize_t n);



#endif
