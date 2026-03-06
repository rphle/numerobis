#ifndef VALUES_H
#define VALUES_H

#include "exceptions/throw.h"
#include "types/methods.h"
#include <glib.h>
#include <stdbool.h>
#include <stdint.h>

typedef enum {
  VALUE_NUMBER,
  VALUE_BOOL,
  VALUE_STR,
  VALUE_LIST,
  VALUE_RANGE,
  VALUE_CLOSURE,
  VALUE_EXTERN_FN,
  VALUE_NONE
} ValueType;
typedef enum { NUM_INT64, NUM_DOUBLE } NumberKind;

struct Value;
typedef struct Range Range;
typedef struct Value Value;

typedef struct {
  NumberKind kind;
  uint64_t unit;
  union {
    gint64 i64;
    gdouble f64;
  };
} Number;

typedef struct {
  Value (*func)(void *env, Value *args);
  void *env;
} Closure;

extern Value closure__call__(Value callee, Value *args);

typedef struct Value {
  ValueType type;
  union {
    Number number;
    bool boolean;
    GString *str;
    GArray *list;
    Range *range;
    Closure *closure;
    Value (*extern_fn)(Value *args);
    void *none;
  };
} Value;

static inline Value __bool__(Value a) {
  return NUMEROBIS_METHODS[a.type]->__bool__(a);
}
static inline bool __cbool__(Value a) {
  return NUMEROBIS_METHODS[a.type]->__cbool__(a);
}

static inline Value __add__(Value self, Value other) {
  return NUMEROBIS_METHODS[self.type]->__add__(self, other);
}
static inline Value __sub__(Value self, Value other) {
  return NUMEROBIS_METHODS[self.type]->__sub__(self, other);
}
static inline Value __mul__(Value self, Value other) {
  return NUMEROBIS_METHODS[self.type]->__mul__(self, other);
}
static inline Value __div__(Value self, Value other) {
  return NUMEROBIS_METHODS[self.type]->__div__(self, other);
}
static inline Value __mod__(Value self, Value other) {
  return NUMEROBIS_METHODS[self.type]->__mod__(self, other);
}
static inline Value __pow__(Value self, Value other) {
  return NUMEROBIS_METHODS[self.type]->__pow__(self, other);
}
static inline Value __dadd__(Value self, Value other) {
  return NUMEROBIS_METHODS[self.type]->__dadd__(self, other);
}
static inline Value __dsub__(Value self, Value other) {
  return NUMEROBIS_METHODS[self.type]->__dsub__(self, other);
}

static inline Value __lt__(Value a, Value b) {
  return NUMEROBIS_METHODS[a.type]->__lt__(a, b);
}
static inline Value __le__(Value a, Value b) {
  return NUMEROBIS_METHODS[a.type]->__le__(a, b);
}
static inline Value __gt__(Value a, Value b) {
  return NUMEROBIS_METHODS[a.type]->__gt__(a, b);
}
static inline Value __ge__(Value a, Value b) {
  return NUMEROBIS_METHODS[a.type]->__ge__(a, b);
}
static inline Value __eq__(Value a, Value b) {
  return NUMEROBIS_METHODS[a.type]->__eq__(a, b);
}

static inline Value __neg__(Value x) {
  return NUMEROBIS_METHODS[x.type]->__neg__(x);
}

static inline Value len(Value a) { return NUMEROBIS_METHODS[a.type]->len(a); }

static inline Value __getitem__(Value self, Value index, const Location *loc) {
  Value r = NUMEROBIS_METHODS[self.type]->__getitem__(self, index);
  if (r.type == VALUE_NONE)
    u_throw(self.type == VALUE_LIST ? 901 : 902, loc);
  return r;
}
static inline Value __setitem__(Value self, Value index, Value value,
                                const Location *loc) {
  Value r = NUMEROBIS_METHODS[self.type]->__setitem__(self, index, value);
  if (r.type == VALUE_NONE)
    u_throw(self.type == VALUE_LIST ? 903 : 904, loc);
  return r;
}
static inline Value __getslice__(Value _self, Value _start, Value _stop,
                                 Value _step) {
  return NUMEROBIS_METHODS[_self.type]->__getslice__(_self, _start, _stop,
                                                     _step);
}

static inline Value __str__(Value self, const Location *loc) {
  return NUMEROBIS_METHODS[self.type]->__str__(self);
}
static inline Value __int__(Value self, const Location *loc) {
  Value r = NUMEROBIS_METHODS[self.type]->__int__(self);
  if (r.type == VALUE_NONE)
    u_throw(301, loc);
  return r;
}
static inline Value __float__(Value self, const Location *loc) {
  Value r = NUMEROBIS_METHODS[self.type]->__float__(self);
  if (r.type == VALUE_NONE)
    u_throw(302, loc);
  return r;
}

static inline Value __call__(Value self, Value *args) {
  switch (self.type) {
  case VALUE_EXTERN_FN:
    return self.extern_fn(args);
  default:
    return closure__call__(self, args);
  }
}

#endif
