#ifndef VALUES_H
#define VALUES_H
#include <glib.h>
#include <stdbool.h>

typedef enum {
  VALUE_NUMBER,
  VALUE_BOOL,
  VALUE_STR,
  VALUE_LIST,
  VALUE_NONE
} ValueType;
typedef enum { NUM_INT64, NUM_DOUBLE } NumberKind;

typedef struct {
  NumberKind kind;
  union {
    gint64 i64;
    gdouble f64;
  };
} Number;

struct Value;
typedef struct Value Value;

typedef struct {
  Value *(*__bool__)(struct Value *self);
  Value *(*__add__)(struct Value *self, struct Value *other);
  Value *(*__mul__)(struct Value *self, struct Value *other);
  Value *(*__lt__)(struct Value *self, struct Value *other);
  Value *(*__le__)(struct Value *self, struct Value *other);
  Value *(*__gt__)(struct Value *self, struct Value *other);
  Value *(*__ge__)(struct Value *self, struct Value *other);
  Value *(*__eq__)(struct Value *self, struct Value *other);
  Value *(*__neg__)(struct Value *self);
  Value *(*len)(struct Value *self);
  Value *(*__getitem__)(struct Value *self, struct Value *index);
  Value *(*__getslice__)(struct Value *_self, struct Value *_start,
                         struct Value *_stop, struct Value *_step);
} ValueMethods;

typedef struct Value {
  ValueType type;
  const ValueMethods *methods;
  union {
    Number *number;
    bool boolean;
    GString *str;
    GArray *list;
    void *none;
  };
} Value;

static inline Value *__bool__(Value *a) { return a->methods->__bool__(a); }
static inline Value *__add__(Value *self, Value *other) {
  return self->methods->__add__(self, other);
}
static inline Value *__mul__(Value *self, Value *other) {
  return self->methods->__mul__(self, other);
}
static inline Value *__lt__(Value *a, Value *b) {
  return a->methods->__lt__(a, b);
}
static inline Value *__le__(Value *a, Value *b) {
  return a->methods->__le__(a, b);
}
static inline Value *__gt__(Value *a, Value *b) {
  return a->methods->__gt__(a, b);
}
static inline Value *__ge__(Value *a, Value *b) {
  return a->methods->__ge__(a, b);
}
static inline Value *__eq__(Value *a, Value *b) {
  return a->methods->__eq__(a, b);
}
static inline Value *__neg__(Value *x) { return x->methods->__neg__(x); }
static inline Value *len(Value *a) { return a->methods->len(a); }
static inline Value *__getitem__(Value *self, Value *index) {
  return self->methods->__getitem__(self, index);
}
static inline Value *__getslice__(Value *_self, struct Value *_start,
                                  struct Value *_stop, struct Value *_step) {
  return _self->methods->__getslice__(_self, _start, _stop, _step);
}

static inline Value *box_bool(bool x) {
  Value *v = g_new(Value, 1);
  v->type = VALUE_BOOL;
  v->boolean = x;
  return v;
}

static inline Value *box_string(GString *x) {
  Value *v = g_new(Value, 1);
  v->type = VALUE_STR;
  v->str = x;
  return v;
}

static inline Value *box_list(GArray *x) {
  Value *v = g_new(Value, 1);
  v->type = VALUE_LIST;
  v->list = x;
  return v;
}

static inline gint64 unbox_int64(Value *v) {
  g_assert(v->type == VALUE_NUMBER && v->number->kind == NUM_INT64);
  return v->number->i64;
}

static inline gdouble unbox_double(Value *v) {
  g_assert(v->type == VALUE_NUMBER && v->number->kind == NUM_DOUBLE);
  return v->number->f64;
}

static inline bool unbox_bool(Value *v) {
  g_assert(v->type == VALUE_BOOL);
  return v->boolean;
}

static inline GString *unbox_string(Value *v) {
  g_assert(v->type == VALUE_STR);
  return v->str;
}

static inline GArray *unbox_list(Value *v) {
  g_assert(v->type == VALUE_LIST);
  return v->list;
}

#endif
