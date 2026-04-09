#include "str.h"
#include "../constants.h"
#include "../libs/sds.h"
#include "../units/units.h"
#include "../utils/utils.h"
#include "../values.h"
#include "bool.h"
#include "methods.h"
#include "number.h"

#include <assert.h>
#include <ctype.h>
#include <gc.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

static const ValueMethods _str_methods;

Value str__init__(sds x) {
  Value v;
  v.type = VALUE_STR;
  v.str = x;
  return v;
}

static const char **build_char_positions(const sds self, size_t len) {
  const char **positions = GC_MALLOC((len + 1) * sizeof(char *));
  const char *p = self;
  const char *end = self + sdslen(self);

  for (size_t i = 0; i < len && p < end; i++) {
    positions[i] = p;
    p = utf8_next_char(p, end);
  }
  positions[len] = end;

  return positions;
}

static Value str__bool__(Value self) {
  return bool__init__(sdslen(self.str) > 0);
}
static bool str__cbool__(Value self) { return sdslen(self.str) > 0; }

static Value str__getitem__(Value _self, Value _index) {
  sds self = _self.str;
  assert(_index.type == VALUE_NUMBER && _index.number.kind == NUM_INT64);
  long index = _index.number.i64;

  if (!self)
    return EMPTY;

  ssize_t len = (ssize_t)_str_len(self);
  ssize_t nidx = normalize_index(index, len);

  if (nidx < 0 || nidx >= len)
    return EMPTY;

  const char *p = self;
  const char *end = self + sdslen(self);
  for (ssize_t i = 0; i < nidx; i++)
    p = utf8_next_char(p, end);

  const char *next = utf8_next_char(p, end);

  return str__init__(sdsnewlen(p, next - p));
}

static Value str__getslice__(Value _self, Value _start, Value _stop,
                             Value _step) {
  sds self = _self.str;
  if (!self)
    return str__init__(sdsempty());

  ssize_t len = (ssize_t)_str_len(self);

  ssize_t start =
      (_start.type == VALUE_NUMBER) ? (ssize_t)_start.number.i64 : SLICE_NONE;
  ssize_t end =
      (_stop.type == VALUE_NUMBER) ? (ssize_t)_stop.number.i64 : SLICE_NONE;
  ssize_t step =
      (_step.type == VALUE_NUMBER) ? (ssize_t)_step.number.i64 : SLICE_NONE;

  if (len == 0 || step == 0)
    return str__init__(sdsempty());

  normalize_slice(len, &start, &end, &step);

  if ((step > 0 && start >= end) || (step < 0 && start <= end))
    return str__init__(sdsempty());

  const char **positions = build_char_positions(self, len);
  sds result = sdsempty();

  for (ssize_t i = start; step > 0 ? i < end : i > end; i += step) {
    if (i >= 0 && i < len) {
      result = sdscatlen(result, positions[i], positions[i + 1] - positions[i]);
    }
  }

  return str__init__(result);
}

static Value str__add__(Value _self, Value _other) {
  sds self = _self.str;
  sds other = _other.str;

  if (!self || !other)
    return str__init__(sdsempty());

  sds result = sdsnewlen(self, sdslen(self));
  result = sdscatlen(result, other, sdslen(other));

  return str__init__(result);
}

static Value str__mul__(Value _self, Value _n) {
  sds self = _self.str;
  long n = _n.number.i64;

  if (!self || n <= 0)
    return str__init__(sdsempty());

  /* Guard overflow */
  unsigned long long total =
      (unsigned long long)sdslen(self) * (unsigned long long)n;
  size_t capacity = (total > UINT_MAX) ? UINT_MAX : (size_t)total;

  sds result = sdsempty();
  result = sdsMakeRoomFor(result, capacity);
  for (ssize_t i = 0; i < n; i++)
    result = sdscatlen(result, self, sdslen(self));

  return str__init__(result);
}

static Value str__eq__(Value a, Value b) {
  if (a.str == b.str)
    return VTRUE;
  if (!a.str || !b.str)
    return VFALSE;
  bool eq = (sdslen(a.str) == sdslen(b.str)) &&
            (memcmp(a.str, b.str, sdslen(a.str)) == 0);
  return bool__init__(eq);
}

static Value str__lt__(Value self, Value other) {
  if (!self.str || !other.str)
    return VFALSE;
  return bool__init__(_str_len(self.str) < _str_len(other.str));
}

static Value str__le__(Value self, Value other) {
  if (!self.str || !other.str)
    return VFALSE;
  return bool__init__(_str_len(self.str) <= _str_len(other.str));
}

static Value str__gt__(Value self, Value other) {
  if (!self.str || !other.str)
    return VFALSE;
  return bool__init__(_str_len(self.str) > _str_len(other.str));
}

static Value str__ge__(Value self, Value other) {
  if (!self.str || !other.str)
    return VFALSE;
  return bool__init__(_str_len(self.str) >= _str_len(other.str));
}

static inline Value str__str__(Value self) { return self; }

static Value str__int__(Value self) {
  const char *str = self.str;
  char *endptr = NULL;

  while (isspace((unsigned char)*str)) {
    str++;
  }

  if (*str == '\0') {
    return EMPTY;
  }

  long result = strtoll(str, &endptr, 10);

  while (isspace((unsigned char)*endptr)) {
    endptr++;
  }

  if (*endptr != '\0') {
    return EMPTY;
  }

  return int__init__(result, U_ONE);
}

static Value str__num__(Value self) {
  if (!self.str)
    return EMPTY;

  const char *str = self.str;
  char *endptr = NULL;

  while (isspace((unsigned char)*str)) {
    str++;
  }

  if (*str == '\0') {
    return EMPTY;
  }

  double result = strtod(str, &endptr);

  while (isspace((unsigned char)*endptr)) {
    endptr++;
  }

  if (*endptr != '\0') {
    return EMPTY;
  }

  return num__init__(result, U_ONE);
}

static const ValueMethods _str_methods = {
    .__bool__ = str__bool__,
    .__cbool__ = str__cbool__,
    .__lt__ = str__lt__,
    .__le__ = str__le__,
    .__gt__ = str__gt__,
    .__ge__ = str__ge__,
    .__eq__ = str__eq__,
    .__getitem__ = str__getitem__,
    .__getslice__ = str__getslice__,
    .__add__ = str__add__,
    .__mul__ = str__mul__,
    .__str__ = str__str__,
    .__int__ = str__int__,
    .__num__ = str__num__,
};

void str_methods_init(void) { NUMEROBIS_METHODS[VALUE_STR] = &_str_methods; }
