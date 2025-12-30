#ifndef CONSTANTS_H
#define CONSTANTS_H

#include "values.h"
#include <stddef.h>

#define SLICE_NONE ((ssize_t)(-999999999))

static inline Value *create_none() {
  Value *v = g_new(Value, 1);
  v->type = VALUE_NONE;
  v->none = NULL;
  return v;
}

#define NONE create_none()

#endif
