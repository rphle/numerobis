#ifndef VALUES_H
#define VALUES_H

#include "exceptions/throw.h"
#include "types/methods.h"

#include <assert.h>
#include <glib.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

typedef enum {
  VALUE_NUMBER,
  VALUE_BOOL,
  VALUE_STR,
  VALUE_LIST,
  VALUE_RANGE,
  VALUE_CLOSURE,
  VALUE_EXTERN_FN,
  VALUE_STRUCT,
  VALUE_NONE,
  VALUE_EMPTY
} ValueType;
typedef enum { NUM_INT64, NUM_DOUBLE } NumberKind;

struct Value;
struct Closure;
typedef struct Range Range;
typedef struct Value Value;

typedef const Location *LocRef;

typedef struct {
  NumberKind kind;
  uint64_t unit;
  union {
    gint64 i64;
    gdouble f64;
  };
} Number;

typedef struct Value {
  ValueType type;
  union {
    Number number;
    bool boolean;
    GString *str;
    GArray *list;
    struct Range *range;
    struct Closure *closure;
    struct Value (*extern_fn)(struct Value *args);
    struct Value *strukt;
    void *none;
  };
} Value;

typedef struct Closure {
  Value (*func)(void *env, Value *args);
  void *env;
  Value bound_arg;
} Closure;

// Helper to tag/untag pointers using the LSB
#define EXTERN_TAG (uintptr_t)0x1
#define TAG_EXTERN(ptr) ((void *)((uintptr_t)(ptr) | EXTERN_TAG))
#define UNTAG_EXTERN(ptr) ((void *)((uintptr_t)(ptr) & ~EXTERN_TAG))
#define IS_EXTERN_CLOSURE(ptr) ((uintptr_t)(ptr) & EXTERN_TAG)
// -------

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

extern Value bool__init__(bool x);

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
  if (a.type != b.type)
    return bool__init__(false);
  return NUMEROBIS_METHODS[a.type]->__eq__(a, b);
}

static inline Value __neg__(Value x) {
  return NUMEROBIS_METHODS[x.type]->__neg__(x);
}

static inline Value __getitem__(Value self, Value index, LocRef loc) {
  Value r = NUMEROBIS_METHODS[self.type]->__getitem__(self, index);
  if (r.type == VALUE_EMPTY)
    u_throw(self.type == VALUE_LIST ? 901 : 902, NULL, loc);
  return r;
}
static inline Value __setitem__(Value self, Value index, Value value,
                                LocRef loc) {
  Value r = NUMEROBIS_METHODS[self.type]->__setitem__(self, index, value);
  if (r.type == VALUE_EMPTY)
    u_throw(self.type == VALUE_LIST ? 903 : 904, NULL, loc);
  return r;
}
static inline Value __getslice__(Value _self, Value _start, Value _stop,
                                 Value _step) {
  return NUMEROBIS_METHODS[_self.type]->__getslice__(_self, _start, _stop,
                                                     _step);
}

extern Value closure__init__(Value (*func)(void *, Value *), void *env,
                             Value bound_arg);

static inline Value __getattr__(Value func, Value self) {
  switch (func.type) {
  case VALUE_CLOSURE:
    // Bind 'self' to a new closure
    return closure__init__(func.closure->func, func.closure->env, self);
  case VALUE_EXTERN_FN:
    // Wrap the extern_fn. NULL for the func pointer because
    // the actual logic will be intercepted by __call__ via the tagged env.
    return closure__init__(NULL, TAG_EXTERN(func.extern_fn), self);
  default:
    g_error("__getattr__: not a closure or extern fn!");
    return (Value){.type = VALUE_NONE};
  }
}

static inline Value __str__(Value self, LocRef loc) {
  return NUMEROBIS_METHODS[self.type]->__str__(self);
}
static inline Value __int__(Value self, LocRef loc) {
  Value r = NUMEROBIS_METHODS[self.type]->__int__(self);
  if (r.type == VALUE_EMPTY)
    u_throw(301, NULL, loc);
  return r;
}
static inline Value __num__(Value self, LocRef loc) {
  Value r = NUMEROBIS_METHODS[self.type]->__num__(self);
  if (r.type == VALUE_EMPTY)
    u_throw(302, NULL, loc);
  return r;
}

static inline Value __call__(Value self, Value *args, size_t argc) {
  if (__builtin_expect(self.type == VALUE_EXTERN_FN, 0)) {
    return self.extern_fn(args);
  }

  Closure *cl = self.closure;

  // Append bound argument if present
  if (__builtin_expect(cl->bound_arg.type != VALUE_EMPTY, 0)) {
    args[argc] = cl->bound_arg;
    // args[argc + 1] = (Value){.type = VALUE_NONE};
    argc++;
  }

  if (IS_EXTERN_CLOSURE(cl->env)) {
    Value (*raw_ext)(Value *) = (Value (*)(Value *))UNTAG_EXTERN(cl->env);
    return raw_ext(args);
  }
  return cl->func(cl->env, args);
}

#endif
