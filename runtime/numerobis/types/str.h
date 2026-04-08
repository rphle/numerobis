#ifndef NUMEROBIS_STR_H
#define NUMEROBIS_STR_H

#include "../libs/sds.h"
#include "../units/units.h"
#include "../utils/utils.h"
#include "../values.h"
#include "number.h"

#include <stddef.h>

Value str__init__(sds x);

#define EMPTY_STR str__init__(sdsempty())

static inline size_t _str_len(const sds s) {
  return s ? count_utf8_code_points(s) : 0;
}

static inline Value str_len(Value self) {
  return int__init__(self.str ? _str_len(self.str) : 0, U_ONE);
}

void str_methods_init(void);

#endif
