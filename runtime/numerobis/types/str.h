#ifndef NUMEROBIS_STR_H
#define NUMEROBIS_STR_H

#include "../units/units.h"
#include "../values.h"
#include "number.h"

#include <glib.h>
#include <stddef.h>

Value str__init__(GString *x);

#define EMPTY_STR str__init__(g_string_new(""))

static inline size_t _str_len(const GString *self) {
  return self ? g_utf8_strlen(self->str, self->len) : 0;
}

static inline Value str_len(Value self) {
  return int__init__(self.str ? _str_len(self.str) : 0, U_ONE);
}

void str_methods_init(void);

#endif
