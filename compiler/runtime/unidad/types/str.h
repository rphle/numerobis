#ifndef UNIDAD_STR_H
#define UNIDAD_STR_H

#include "../values.h"
#include <glib.h>
#include <stddef.h>

Value *str__init__(GString *x);

size_t str_len(const GString *self);


#endif
