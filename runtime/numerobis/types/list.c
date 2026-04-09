#include "list.h"
#include "../constants.h"
#include "../extern.h"
#include "../libs/gc_stb_ds.h"
#include "../libs/sds.h"
#include "../utils/utils.h"
#include "../values.h"
#include "bool.h"
#include "methods.h"
#include "str.h"

#include <gc/gc.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

static const ValueMethods _list_methods;

Value list__init__(Value *items) {
  Value v;
  v.type = VALUE_LIST;

  List *obj = GC_MALLOC(sizeof(List));
  obj->items = items;

  v.list = (void *)obj;
  return v;
}

Value list_of(const Value *items, size_t len) {
  Value *result = NULL;

  arrsetcap(result, len);

  for (size_t i = 0; i < len; i++) {
    arrput(result, items[i]);
  }

  return list__init__(result);
}

static Value list__bool__(Value self) {
  return bool__init__(_list_len((List *)self.list) > 0);
}

static bool list__cbool__(Value self) {
  return _list_len((List *)self.list) > 0;
}

static Value list__getitem__(Value _self, Value _index) {
  List *self = (List *)_self.list;
  assert(_index.type == VALUE_NUMBER);

  ssize_t index = (ssize_t)_index.number.i64;
  ssize_t len = (ssize_t)_list_len(self);

  if (len == 0)
    return EMPTY;

  ssize_t nidx = normalize_index(index, len);

  if (nidx < 0 || nidx >= len)
    return EMPTY;

  return self->items[nidx];
}

static Value list__getslice__(Value _self, Value _start, Value _stop,
                              Value _step) {
  List *self = (List *)_self.list;

  ssize_t len = (ssize_t)_list_len(self);
  ssize_t start =
      (_start.type == VALUE_NUMBER) ? (ssize_t)_start.number.i64 : SLICE_NONE;
  ssize_t end =
      (_stop.type == VALUE_NUMBER) ? (ssize_t)_stop.number.i64 : SLICE_NONE;
  ssize_t step =
      (_step.type == VALUE_NUMBER) ? (ssize_t)_step.number.i64 : SLICE_NONE;
  Value *result = NULL;

  if (len == 0 || step == 0)
    return list__init__(result);

  normalize_slice(len, &start, &end, &step);

  for (ssize_t i = start; step > 0 ? i < end : i > end; i += step) {
    Value val = self->items[i];
    arrput(result, val);
  }

  return list__init__(result);
}

static Value list__add__(Value _self, Value _other) {
  List *self = (List *)_self.list;
  List *other = (List *)_other.list;

  size_t a_len = _list_len(self);
  size_t b_len = _list_len(other);
  Value *result = NULL;

  arrsetcap(result, a_len + b_len);

  for (size_t i = 0; i < a_len; i++) {
    arrput(result, self->items[i]);
  }
  for (size_t i = 0; i < b_len; i++) {
    arrput(result, other->items[i]);
  }

  return list__init__(result);
}

static Value list__mul__(Value _self, Value _n) {
  List *self = (List *)_self.list;
  assert(_n.type == VALUE_NUMBER && _n.number.kind == NUM_INT64);

  ssize_t n = (ssize_t)_n.number.i64;
  size_t len = _list_len(self);

  if (n <= 0 || len == 0)
    return list__init__(NULL);

  unsigned long long total = (unsigned long long)len * (unsigned long long)n;
  size_t reserve = (size_t)total;
  Value *result = NULL;
  arrsetcap(result, reserve);

  for (ssize_t r = 0; r < n; r++) {
    for (size_t i = 0; i < len; i++) {
      arrput(result, self->items[i]);
    }
  }

  return list__init__(result);
}

// Mutation

static Value list_append(Value *args) {
  Value _self = args[2];
  Value val = args[1];
  if (_self.type == VALUE_LIST && _self.list) {
    List *self = (List *)_self.list;
    arrput(self->items, val);
  }
  return NONE;
}

static Value list_extend(Value *args) {
  Value _self = args[2];
  Value _other = args[1];

  if (_self.type != VALUE_LIST || !_self.list || _other.type != VALUE_LIST ||
      !_other.list)
    return EMPTY;

  List *self = (List *)_self.list;
  List *other = (List *)_other.list;
  size_t other_len = _list_len(other);

  for (size_t i = 0; i < other_len; i++) {
    arrput(self->items, other->items[i]);
  }

  return NONE;
}

static Value list_insert(Value *args) {
  Value _self = args[3];
  Value _index = args[1];
  Value val = args[2];

  if (_self.type != VALUE_LIST || !_self.list)
    return EMPTY;

  List *self = (List *)_self.list;
  long idx_raw = (_index.type == VALUE_NUMBER) ? _index.number.i64 : 0;
  ssize_t index = (ssize_t)idx_raw;
  ssize_t len = (ssize_t)_list_len(self);

  if (index < 0) {
    index += len;
    if (index < 0)
      index = 0;
  }

  if (index > len)
    index = len;

  arrins(self->items, (int)index, val);
  return NONE;
}

Value list__setitem__(Value _self, Value _index, Value val) {
  if (_self.type != VALUE_LIST || !_self.list)
    return EMPTY;

  List *self = (List *)_self.list;
  assert(_index.type == VALUE_NUMBER);

  ssize_t index = (ssize_t)_index.number.i64;
  ssize_t len = (ssize_t)_list_len(self);
  ssize_t nidx = normalize_index(index, len);

  if (nidx < 0 || nidx >= len)
    return EMPTY;

  self->items[nidx] = val;
  return val;
}

Value list__delitem__(Value _self, Value _index) {
  if (_self.type != VALUE_LIST || !_self.list)
    return EMPTY;

  List *self = (List *)_self.list;
  assert(_index.type == VALUE_NUMBER);

  ssize_t index = (ssize_t)_index.number.i64;
  ssize_t len = (ssize_t)_list_len(self);

  ssize_t nidx = normalize_index(index, len);
  if (nidx < 0 || nidx >= len)
    return EMPTY;

  arrdel(self->items, (int)nidx);
  return NONE;
}

static Value list_pop(Value *args) {
  Value _self = args[2];
  Value _index = args[1];

  if (_self.type != VALUE_LIST || !_self.list ||
      _list_len((List *)_self.list) == 0)
    return EMPTY;

  List *self = (List *)_self.list;
  ssize_t len = (ssize_t)_list_len(self);
  ssize_t idx;

  if (_index.type == VALUE_EMPTY)
    idx = len - 1;
  else {
    assert(_index.type == VALUE_NUMBER);
    idx = (ssize_t)_index.number.i64;
  }

  ssize_t nidx = normalize_index(idx, len);
  if (nidx < 0 || nidx >= len)
    return EMPTY;

  Value result = self->items[nidx];
  arrdel(self->items, (int)nidx);
  return result;
}

// Comparison

static Value list__eq__(Value a, Value b) {
  if (a.list == b.list)
    return VTRUE;
  if (a.type != VALUE_LIST || b.type != VALUE_LIST)
    return VFALSE;

  List *al = (List *)a.list;
  List *bl = (List *)b.list;
  size_t len = _list_len(al);

  if (len != _list_len(bl))
    return VFALSE;

  for (size_t i = 0; i < len; i++) {
    Value val_a = al->items[i];
    Value val_b = bl->items[i];

    Value eq_result = __eq__(val_a, val_b);
    if (!eq_result.boolean)
      return VFALSE;
  }

  return VTRUE;
}

static Value list__lt__(Value self, Value other) {
  return bool__init__(_list_len((List *)self.list) <
                      _list_len((List *)other.list));
}

static Value list__le__(Value self, Value other) {
  return bool__init__(_list_len((List *)self.list) <=
                      _list_len((List *)other.list));
}

static Value list__gt__(Value self, Value other) {
  return bool__init__(_list_len((List *)self.list) >
                      _list_len((List *)other.list));
}

static Value list__ge__(Value self, Value other) {
  return bool__init__(_list_len((List *)self.list) >=
                      _list_len((List *)other.list));
}

// serialization
static Value list__str__(Value self) {
  sds result = sdsnew("[");
  List *arr = (List *)self.list;
  size_t len = _list_len(arr);

  for (size_t i = 0; i < len; i++) {
    if (i > 0)
      result = sdscat(result, ", ");

    Value elem = arr->items[i];
    if (elem.type == VALUE_STR) {
      result = sdscatprintf(result, "\"%s\"", elem.str);
    } else {
      Value elem_str = __str__(elem, NULL);
      result = sdscat(result, elem_str.str);
    }
  }
  result = sdscat(result, "]");

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
