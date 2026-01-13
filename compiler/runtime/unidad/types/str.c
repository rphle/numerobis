#include "../constants.h"
#include "../utils/utils.h"
#include "../values.h"
#include "bool.h"
#include "number.h"
#include <glib.h>
#include <stdbool.h>
#include <stddef.h>

static const ValueMethods _str_methods;

Value *str__init__(GString *x) {
  Value *v = g_new(Value, 1);
  v->type = VALUE_STR;
  v->str = x;
  v->methods = &_str_methods;
  return v;
}

static inline size_t _str_len(const GString *self) {
  return self ? g_utf8_strlen(self->str, self->len) : 0;
}

static inline Value *str_len(Value *self) {
  return int__init__(self ? _str_len(self->str) : 0, U_ONE);
}

static const char **build_char_positions(const GString *self, size_t len) {
  const char **positions = g_malloc((len + 1) * sizeof(char *));
  const char *p = self->str;
  const char *end = self->str + self->len;

  for (size_t i = 0; i < len && p < end; i++) {
    positions[i] = p;
    p = g_utf8_next_char(p);
  }
  positions[len] = end;

  return positions;
}

static Value *str__bool__(Value *self) {
  return bool__init__(self->str->len > 0);
}
static bool str__cbool__(Value *self) { return self->str->len > 0; }

static Value *str__getitem__(Value *_self, Value *_index) {
  GString *self = _self->str;
  g_assert(_index->type == VALUE_NUMBER && _index->number->kind == NUM_INT64);
  gint64 index = _index->number->i64;

  if (!self)
    return NULL;

  ssize_t len = (ssize_t)_str_len(self);
  ssize_t nidx = normalize_index(index, len);

  if (nidx < 0 || nidx >= len)
    return NULL;

  const char *p = self->str;
  for (ssize_t i = 0; i < nidx; i++)
    p = g_utf8_next_char(p);

  gunichar ch = g_utf8_get_char(p);
  gchar buf[8];
  gint utf8_len = g_unichar_to_utf8(ch, buf);
  buf[utf8_len] = '\0';

  return str__init__(g_string_new(buf));
}

static Value *str__getslice__(Value *_self, Value *_start, Value *_stop,
                              Value *_step) {
  GString *self = _self->str;
  if (!self)
    return str__init__(g_string_new(""));

  ssize_t len = (ssize_t)_str_len(self);

  ssize_t start = (_start->type == VALUE_NUMBER) ? (ssize_t)_start->number->i64
                                                 : SLICE_NONE;
  ssize_t end =
      (_stop->type == VALUE_NUMBER) ? (ssize_t)_stop->number->i64 : SLICE_NONE;
  ssize_t step =
      (_step->type == VALUE_NUMBER) ? (ssize_t)_step->number->i64 : SLICE_NONE;

  if (len == 0 || step == 0)
    return str__init__(g_string_new(""));

  normalize_slice(len, &start, &end, &step);

  if ((step > 0 && start >= end) || (step < 0 && start <= end))
    return str__init__(g_string_new(""));

  const char **positions = build_char_positions(self, len);
  GString *result = g_string_new("");

  for (ssize_t i = start; step > 0 ? i < end : i > end; i += step) {
    if (i >= 0 && i < len) {
      g_string_append_len(result, positions[i],
                          positions[i + 1] - positions[i]);
    }
  }

  g_free(positions);
  return str__init__(result);
}

static Value *str__setitem__(Value *_self, Value *_index, Value *_value) {
  GString *self = _self->str;
  g_assert(_index->type == VALUE_NUMBER && _index->number->kind == NUM_INT64);
  g_assert(_value->type == VALUE_STR);

  gint64 index = _index->number->i64;
  GString *value = _value->str;

  if (!self || !value)
    return NULL;

  ssize_t len = (ssize_t)_str_len(self);
  ssize_t nidx = normalize_index(index, len);

  if (nidx < 0 || nidx >= len)
    return NULL;

  const char *p = self->str;
  for (ssize_t i = 0; i < nidx; i++)
    p = g_utf8_next_char(p);

  const char *next = g_utf8_next_char(p);
  gint old_char_len = next - p;

  // get the new char (first character of value str)
  gunichar new_ch = g_utf8_get_char(value->str);
  gchar buf[8];
  gint new_char_len = g_unichar_to_utf8(new_ch, buf);

  gint offset = p - self->str;

  g_string_erase(self, offset, old_char_len);
  g_string_insert_len(self, offset, buf, new_char_len);

  return _self;
}

static Value *str__add__(Value *_self, Value *_other) {
  GString *self = _self->str;
  GString *other = _other->str;

  if (!self || !other)
    return str__init__(g_string_new(""));

  GString *result = g_string_sized_new(self->len + other->len);
  g_string_append_len(result, self->str, self->len);
  g_string_append_len(result, other->str, other->len);

  return str__init__(result);
}

static Value *str__mul__(Value *_self, Value *_n) {
  GString *self = _self->str;
  gint64 n = _n->number->i64;

  if (!self || n <= 0)
    return str__init__(g_string_new(""));

  /* Guard overflow */
  unsigned long long total =
      (unsigned long long)self->len * (unsigned long long)n;
  size_t capacity = (total > G_MAXUINT) ? G_MAXUINT : (size_t)total;

  GString *result = g_string_sized_new(capacity);
  for (ssize_t i = 0; i < n; i++)
    g_string_append_len(result, self->str, self->len);

  return str__init__(result);
}

static Value *str__eq__(Value *a, Value *b) {
  if (a == b)
    return VTRUE;
  if (!a || !b)
    return VFALSE;
  return bool__init__(g_string_equal(a->str, b->str));
}

static Value *str__lt__(Value *self, Value *other) {
  if (!self || !other)
    return VFALSE;
  return bool__init__(_str_len(self->str) < _str_len(other->str));
}

static Value *str__le__(Value *self, Value *other) {
  if (!self || !other)
    return VFALSE;
  return bool__init__(_str_len(self->str) <= _str_len(other->str));
}

static Value *str__gt__(Value *self, Value *other) {
  if (!self || !other)
    return VFALSE;
  return bool__init__(_str_len(self->str) > _str_len(other->str));
}

static Value *str__ge__(Value *self, Value *other) {
  if (!self || !other)
    return VFALSE;
  return bool__init__(_str_len(self->str) >= _str_len(other->str));
}

static inline Value *str__str__(Value *self) { return self; }

static Value *str__int__(Value *self) {
  const gchar *str = self->str->str;
  gchar *endptr = NULL;

  while (g_ascii_isspace(*str)) {
    str++;
  }

  if (*str == '\0') {
    return NULL;
  }

  gint64 result = g_ascii_strtoll(str, &endptr, 10);

  while (g_ascii_isspace(*endptr)) {
    endptr++;
  }

  if (*endptr != '\0') {
    return NULL;
  }

  return int__init__(result, U_ONE);
}

static const ValueMethods _str_methods = {
    .__bool__ = str__bool__,
    .__cbool__ = str__cbool__,
    .__lt__ = str__lt__,
    .__le__ = str__le__,
    .__gt__ = str__gt__,
    .__ge__ = str__ge__,
    .__eq__ = str__eq__,
    .len = str_len,
    .__getitem__ = str__getitem__,
    .__setitem__ = str__setitem__,
    .__getslice__ = str__getslice__,
    .__add__ = str__add__,
    .__mul__ = str__mul__,
    .__str__ = str__str__,
    .__int__ = str__int__,
};
