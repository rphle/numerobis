#include "list.h"
#include "../constants.h"
#include "../extern.h"
#include "../utils/utils.h"
#include "../values.h"
#include "bool.h"
#include "methods.h"
#include "str.h"

#include <glib.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

static const ValueMethods _list_methods;

Value list__init__(GArray *x) {
  Value v;
  v.type = VALUE_LIST;
  v.list = x;
  return v;
}

Value list_of(const Value *items, size_t len) {
  GArray *result = g_array_new(FALSE, FALSE, sizeof(Value));

  for (size_t i = 0; i < len; i++) {
    g_array_append_val(result, items[i]);
  }

  return list__init__(result);
}

static Value list__bool__(Value self) {
  return bool__init__(_list_len(self.list) > 0);
}
static bool list__cbool__(Value self) { return _list_len(self.list) > 0; }

static Value list__getitem__(Value _self, Value _index) {
  GArray *self = _self.list;
  g_assert(_index.type == VALUE_NUMBER);
  ssize_t index = (ssize_t)_index.number.i64;

  ssize_t len = (ssize_t)_list_len(self);
  if (len == 0)
    return EMPTY;

  ssize_t nidx = normalize_index(index, len);
  if (nidx < 0 || nidx >= len)
    return EMPTY;

  return g_array_index(self, Value, (unsigned int)nidx);
}

static Value list__getslice__(Value _self, Value _start, Value _stop,
                              Value _step) {
  GArray *self = _self.list;
  ssize_t len = (ssize_t)_list_len(self);

  ssize_t start =
      (_start.type == VALUE_NUMBER) ? (ssize_t)_start.number.i64 : SLICE_NONE;
  ssize_t end =
      (_stop.type == VALUE_NUMBER) ? (ssize_t)_stop.number.i64 : SLICE_NONE;
  ssize_t step =
      (_step.type == VALUE_NUMBER) ? (ssize_t)_step.number.i64 : SLICE_NONE;

  GArray *result = g_array_new(FALSE, FALSE, sizeof(Value));
  if (len == 0 || step == 0)
    return list__init__(result);

  normalize_slice(len, &start, &end, &step);

  for (ssize_t i = start; step > 0 ? i < end : i > end; i += step) {
    Value val = g_array_index(self, Value, (unsigned int)i);
    g_array_append_val(result, val);
  }

  return list__init__(result);
}

static Value list__add__(Value _self, Value _other) {
  GArray *self = _self.list;
  GArray *other = _other.list;

  size_t a_len = _list_len(self);
  size_t b_len = _list_len(other);
  GArray *result = g_array_sized_new(FALSE, FALSE, sizeof(Value),
                                     (unsigned int)(a_len + b_len));

  for (unsigned int i = 0; i < (unsigned int)a_len; i++) {
    Value val = g_array_index(self, Value, i);
    g_array_append_val(result, val);
  }

  for (unsigned int i = 0; i < (unsigned int)b_len; i++) {
    Value val = g_array_index(other, Value, i);
    g_array_append_val(result, val);
  }

  return list__init__(result);
}

static Value list__mul__(Value _self, Value _n) {
  GArray *self = _self.list;
  g_assert(_n.type == VALUE_NUMBER && _n.number.kind == NUM_INT64);
  ssize_t n = (ssize_t)_n.number.i64;

  size_t len = _list_len(self);
  if (n <= 0 || len == 0)
    return list__init__(g_array_new(FALSE, FALSE, sizeof(Value)));

  unsigned long long total = (unsigned long long)len * (unsigned long long)n;
  unsigned int reserve = (total > G_MAXUINT) ? G_MAXUINT : (unsigned int)total;
  GArray *result = g_array_sized_new(FALSE, FALSE, sizeof(Value), reserve);

  for (ssize_t r = 0; r < n; r++) {
    for (unsigned int i = 0; i < (unsigned int)len; i++) {
      Value original = g_array_index(self, Value, i);
      g_array_append_val(result, original);
    }
  }

  return list__init__(result);
}

// Mutation

static Value list_append(Value *args) {
  Value _self = args[2];
  Value val = args[1];
  if (_self.type == VALUE_LIST && _self.list) {
    g_array_append_val(_self.list, val);
  }
  return NONE;
}

static Value list_extend(Value *args) {
  Value _self = args[2];
  Value _other = args[1];

  if (_self.type != VALUE_LIST || !_self.list || _other.type != VALUE_LIST ||
      !_other.list)
    return EMPTY;

  GArray *self = _self.list;
  GArray *other = _other.list;

  for (unsigned int i = 0; i < other->len; i++) {
    Value original_val = g_array_index(other, Value, i);
    g_array_append_val(self, original_val);
  }
  return NONE;
}

static Value list_insert(Value *args) {
  Value _self = args[3];
  Value _index = args[1];
  Value val = args[2];
  if (_self.type != VALUE_LIST || !_self.list)
    return EMPTY;

  GArray *self = _self.list;

  long idx_raw = (_index.type == VALUE_NUMBER) ? _index.number.i64 : 0;
  ssize_t index = (ssize_t)idx_raw;
  ssize_t len = (ssize_t)self->len;

  if (index < 0) {
    index += len;
    if (index < 0)
      index = 0;
  }
  if (index > len)
    index = len;

  g_array_insert_val(self, (unsigned int)index, val);
  return NONE;
}

Value list__setitem__(Value _self, Value _index, Value val) {
  if (_self.type != VALUE_LIST || !_self.list)
    return EMPTY;

  GArray *self = _self.list;
  g_assert(_index.type == VALUE_NUMBER);
  ssize_t index = (ssize_t)_index.number.i64;
  ssize_t len = (ssize_t)self->len;

  ssize_t nidx = normalize_index(index, len);
  if (nidx < 0 || nidx >= len)
    return EMPTY;

  g_array_index(self, Value, (unsigned int)nidx) = val;
  return val;
}

Value list__delitem__(Value _self, Value _index) {
  if (_self.type != VALUE_LIST || !_self.list)
    return EMPTY;

  GArray *self = _self.list;
  g_assert(_index.type == VALUE_NUMBER);
  ssize_t index = (ssize_t)_index.number.i64;
  ssize_t len = (ssize_t)self->len;

  ssize_t nidx = normalize_index(index, len);
  if (nidx < 0 || nidx >= len)
    return EMPTY;

  g_array_remove_index(self, (unsigned int)nidx);
  return NONE;
}

static Value list_pop(Value *args) {
  Value _self = args[2];
  Value _index = args[1];
  if (_self.type != VALUE_LIST || !_self.list || _self.list->len == 0)
    return EMPTY;

  GArray *self = _self.list;
  ssize_t len = (ssize_t)self->len;
  ssize_t idx;

  if (_index.type == VALUE_EMPTY) {
    idx = len - 1;
  } else {
    g_assert(_index.type == VALUE_NUMBER);
    idx = (ssize_t)_index.number.i64;
  }

  ssize_t nidx = normalize_index(idx, len);
  if (nidx < 0 || nidx >= len)
    return EMPTY;

  Value result = g_array_index(self, Value, (unsigned int)nidx);
  g_array_remove_index(self, (unsigned int)nidx);
  return result;
}

// Comparison

static Value list__eq__(Value a, Value b) {
  if (a.list == b.list)
    return VTRUE;
  if (a.type != VALUE_LIST || b.type != VALUE_LIST)
    return VFALSE;

  GArray *al = a.list;
  GArray *bl = b.list;

  if (al->len != bl->len)
    return VFALSE;

  for (unsigned int i = 0; i < al->len; i++) {
    Value val_a = g_array_index(al, Value, i);
    Value val_b = g_array_index(bl, Value, i);

    Value eq_result = __eq__(val_a, val_b);
    if (!eq_result.boolean)
      return VFALSE;
  }

  return VTRUE;
}

static Value list__lt__(Value self, Value other) {
  return bool__init__(_list_len(self.list) < _list_len(other.list));
}

static Value list__le__(Value self, Value other) {
  return bool__init__(_list_len(self.list) <= _list_len(other.list));
}

static Value list__gt__(Value self, Value other) {
  return bool__init__(_list_len(self.list) > _list_len(other.list));
}

static Value list__ge__(Value self, Value other) {
  return bool__init__(_list_len(self.list) >= _list_len(other.list));
}

// serialization
static Value list__str__(Value self) {
  GString *result = g_string_new("");

  g_string_append_c(result, '[');
  GArray *arr = self.list;
  for (size_t i = 0; i < arr->len; i++) {
    if (i > 0)
      g_string_append(result, ", ");

    Value elem = g_array_index(arr, Value, i);
    if (elem.type == VALUE_STR) {
      g_string_append_printf(result, "\"%s\"", elem.str->str);
    } else {
      Value elem_str = __str__(elem, NULL);
      g_string_append(result, elem_str.str->str);
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
    .__getitem__ = list__getitem__,
    .__setitem__ = list__setitem__,
    .__getslice__ = list__getslice__,
    .__add__ = list__add__,
    .__mul__ = list__mul__,
    .__str__ = list__str__,
};

void list_methods_init(void) { NUMEROBIS_METHODS[VALUE_LIST] = &_list_methods; }

void numerobis_list_register_externs(void) {
  u_extern_register("List.append", list_append);
  u_extern_register("List.extend", list_extend);
  u_extern_register("List.insert", list_insert);
  u_extern_register("List.pop", list_pop);
}
