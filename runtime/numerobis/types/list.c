#include "list.h"
#include "../constants.h"
#include "../utils/utils.h"
#include "../values.h"
#include "bool.h"
#include "number.h"
#include "str.h"
#include <glib.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

static const ValueMethods _list_methods;

Value *list__init__(GArray *x) {
  Value *v = g_new(Value, 1);
  v->type = VALUE_LIST;
  v->list = x;
  v->methods = &_list_methods;
  return v;
}

static inline size_t _list_len(const GArray *self) {
  return self ? self->len : 0;
}

static Value *list_len(Value *self) {
  return int__init__((gint64)_list_len(self->list), U_ONE);
}

Value *list_of(Value *first, ...) {
  GArray *result = g_array_new(FALSE, FALSE, sizeof(Value *));

  if (!first)
    return list__init__(result);

  va_list ap;
  va_start(ap, first);

  Value *current = first;
  while (current) {
    g_array_append_val(result, current);
    current = va_arg(ap, Value *);
  }

  va_end(ap);
  return list__init__(result);
}

static Value *list__bool__(Value *self) {
  return bool__init__(_list_len(self->list) > 0);
}
static bool list__cbool__(Value *self) { return _list_len(self->list) > 0; }

static Value *list__getitem__(Value *_self, Value *_index) {
  GArray *self = _self->list;
  ssize_t index = (ssize_t)_index->number->i64;

  ssize_t len = (ssize_t)_list_len(self);
  if (len == 0)
    return NULL;

  ssize_t nidx = normalize_index(index, len);
  if (nidx < 0 || nidx >= len)
    return NULL;

  return g_array_index(self, Value *, (guint)nidx);
}

static Value *list__getslice__(Value *_self, Value *_start, Value *_stop,
                               Value *_step) {
  GArray *self = _self->list;
  ssize_t len = (ssize_t)_list_len(self);

  ssize_t start = (_start->type == VALUE_NUMBER) ? (ssize_t)_start->number->i64
                                                 : SLICE_NONE;
  ssize_t end =
      (_stop->type == VALUE_NUMBER) ? (ssize_t)_stop->number->i64 : SLICE_NONE;
  ssize_t step =
      (_step->type == VALUE_NUMBER) ? (ssize_t)_step->number->i64 : SLICE_NONE;

  GArray *result = g_array_new(FALSE, FALSE, sizeof(Value *));
  if (len == 0 || step == 0)
    return list__init__(result);

  normalize_slice(len, &start, &end, &step);

  for (ssize_t i = start; step > 0 ? i < end : i > end; i += step) {
    Value *val = g_array_index(self, Value *, (guint)i);
    g_array_append_val(result, val);
  }

  return list__init__(result);
}

static Value *list__add__(Value *_self, Value *_other) {
  GArray *self = _self->list;
  GArray *other = _other->list;

  size_t a_len = _list_len(self);
  size_t b_len = _list_len(other);
  GArray *result =
      g_array_sized_new(FALSE, FALSE, sizeof(Value *), (guint)(a_len + b_len));

  for (guint i = 0; i < (guint)a_len; i++) {
    Value *val = g_array_index(self, Value *, i);
    g_array_append_val(result, val);
  }

  for (guint i = 0; i < (guint)b_len; i++) {
    Value *val = g_array_index(other, Value *, i);
    g_array_append_val(result, val);
  }

  return list__init__(result);
}

static Value *list__mul__(Value *_self, Value *_n) {
  GArray *self = _self->list;
  g_assert(_n->type == VALUE_NUMBER && _n->number->kind == NUM_INT64);
  ssize_t n = (ssize_t)_n->number->i64;

  size_t len = _list_len(self);
  if (n <= 0 || len == 0)
    return list__init__(g_array_new(FALSE, FALSE, sizeof(Value *)));

  unsigned long long total = (unsigned long long)len * (unsigned long long)n;
  guint reserve = (total > G_MAXUINT) ? G_MAXUINT : (guint)total;
  GArray *result = g_array_sized_new(FALSE, FALSE, sizeof(Value *), reserve);

  for (ssize_t r = 0; r < n; r++) {
    for (guint i = 0; i < (guint)len; i++) {
      Value *val = g_array_index(self, Value *, i);
      g_array_append_val(result, val);
    }
  }

  return list__init__(result);
}

// Mutation

Value *list_append(Value *_self, Value *val) {
  if (_self && _self->list) {
    g_array_append_val(_self->list, val);
  }
  return NONE;
}

Value *list_extend(Value *_self, Value *_other) {
  if (!_self || !_self->list || !_other || !_other->list)
    return NONE;

  GArray *self = _self->list;
  GArray *other = _other->list;

  for (guint i = 0; i < other->len; i++) {
    Value *val = g_array_index(other, Value *, i);
    g_array_append_val(self, val);
  }
  return NONE;
}

Value *list_insert(Value *_self, Value *_index, Value *val) {
  if (!_self || !_self->list)
    return NONE;

  GArray *self = _self->list;

  gint64 idx_raw = (_index->type == VALUE_NUMBER) ? _index->number->i64 : 0;
  ssize_t index = (ssize_t)idx_raw;
  ssize_t len = (ssize_t)self->len;

  if (index < 0) {
    index += len;
    if (index < 0)
      index = 0;
  }
  if (index > len)
    index = len;

  g_array_insert_val(self, (guint)index, val);
  return NONE;
}

Value *list__setitem__(Value *_self, Value *_index, Value *val) {
  if (!_self || !_self->list)
    return NULL;

  GArray *self = _self->list;
  g_assert(_index->type == VALUE_NUMBER);
  ssize_t index = (ssize_t)_index->number->i64;
  ssize_t len = (ssize_t)self->len;

  ssize_t nidx = normalize_index(index, len);
  if (nidx < 0 || nidx >= len)
    return NULL;

  g_array_index(self, Value *, (guint)nidx) = val;
  return NONE;
}

Value *list__delitem__(Value *_self, Value *_index) {
  if (!_self || !_self->list)
    return NONE;

  GArray *self = _self->list;
  g_assert(_index->type == VALUE_NUMBER);
  ssize_t index = (ssize_t)_index->number->i64;
  ssize_t len = (ssize_t)self->len;

  ssize_t nidx = normalize_index(index, len);
  if (nidx < 0 || nidx >= len)
    return NONE;

  g_array_remove_index(self, (guint)nidx);
  return NONE;
}

Value *list_pop(Value *_self, Value *_index) {
  if (!_self || !_self->list || _self->list->len == 0)
    return NONE; // IndexError

  GArray *self = _self->list;
  ssize_t len = (ssize_t)self->len;
  ssize_t idx;

  if (!_index || _index->type == VALUE_NONE) {
    idx = len - 1;
  } else {
    g_assert(_index->type == VALUE_NUMBER);
    idx = (ssize_t)_index->number->i64;
  }

  ssize_t nidx = normalize_index(idx, len);
  if (nidx < 0 || nidx >= len)
    return NONE;

  Value *val = g_array_index(self, Value *, (guint)nidx);
  g_array_remove_index(self, (guint)nidx);
  return val;
}

// Comparison

static Value *list__eq__(Value *a, Value *b) {
  if (a == b)
    return VTRUE;
  if (a->type != VALUE_LIST || b->type != VALUE_LIST)
    return VFALSE;

  GArray *al = a->list;
  GArray *bl = b->list;

  if (al->len != bl->len)
    return VFALSE;

  for (guint i = 0; i < al->len; i++) {
    Value *val_a = g_array_index(al, Value *, i);
    Value *val_b = g_array_index(bl, Value *, i);

    if (!(__eq__(val_a, val_b)->boolean))
      return VFALSE;
  }

  return VTRUE;
}

static Value *list__lt__(Value *self, Value *other) {
  return bool__init__(_list_len(self->list) < _list_len(other->list));
}

static Value *list__le__(Value *self, Value *other) {
  return bool__init__(_list_len(self->list) <= _list_len(other->list));
}

static Value *list__gt__(Value *self, Value *other) {
  return bool__init__(_list_len(self->list) > _list_len(other->list));
}

static Value *list__ge__(Value *self, Value *other) {
  return bool__init__(_list_len(self->list) >= _list_len(other->list));
}

// serialization
static Value *list__str__(Value *self) {
  GString *result = g_string_new("");

  g_string_append_c(result, '[');
  GArray *arr = self->list;
  for (size_t i = 0; i < arr->len; i++) {
    if (i > 0)
      g_string_append(result, ", ");

    Value *elem = g_array_index(arr, Value *, i);
    if (elem && elem->type == VALUE_STR) {
      g_string_append_printf(result, "\"%s\"", elem->str->str);
    } else {
      // recursively convert
      Value *elem_str = list__str__(elem);
      g_string_append(result, elem_str->str->str);
    }
  }
  g_string_append_c(result, ']');

  return str__init__(result);
}

static const ValueMethods _list_methods = {
    .__bool__ = list__bool__,
    .__cbool__ = list__cbool__,
    .__lt__ = list__lt__,
    .__le__ = list__le__,
    .__gt__ = list__gt__,
    .__ge__ = list__ge__,
    .__eq__ = list__eq__,
    .len = list_len,
    .__getitem__ = list__getitem__,
    .__setitem__ = list__setitem__,
    .__getslice__ = list__getslice__,
    .__add__ = list__add__,
    .__mul__ = list__mul__,
    .__str__ = list__str__,
};
