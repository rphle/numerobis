#ifndef WRAPPERS_H
#define WRAPPERS_H
#include <glib.h>
#include <stdbool.h>

typedef enum { VALUE_NUMBER, VALUE_BOOL, VALUE_STRING, VALUE_LIST } ValueType;
typedef enum { NUM_INT64, NUM_DOUBLE } NumberKind;

typedef struct {
  NumberKind kind;
  union {
    gint64 i64;
    gdouble f64;
  };
} Number;

typedef struct Value {
  ValueType type;
  union {
    Number *number;
    bool boolean;
    GString *string;
    GArray *list;
  };
} Value;

static inline Value *box_int64(gint64 x) {
  Number *n = g_new(Number, 1);
  n->kind = NUM_INT64;
  n->i64 = x;
  Value *v = g_new(Value, 1);
  v->type = VALUE_NUMBER;
  v->number = n;
  return v;
}

static inline Value *box_double(gdouble x) {
  Number *n = g_new(Number, 1);
  n->kind = NUM_DOUBLE;
  n->f64 = x;
  Value *v = g_new(Value, 1);
  v->type = VALUE_NUMBER;
  v->number = n;
  return v;
}

static inline Value *box_bool(bool x) {
  Value *v = g_new(Value, 1);
  v->type = VALUE_BOOL;
  v->boolean = x;
  return v;
}

static inline Value *box_string(GString *x) {
  Value *v = g_new(Value, 1);
  v->type = VALUE_STRING;
  v->string = x;
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
  g_assert(v->type == VALUE_STRING);
  return v->string;
}

static inline GArray *unbox_list(Value *v) {
  g_assert(v->type == VALUE_LIST);
  return v->list;
}

#define BOX(x)                                                                 \
  _Generic((x),                                                                \
      gint64: box_int64,                                                       \
      gdouble: box_double,                                                     \
      bool: box_bool,                                                          \
      GString *: box_string,                                                   \
      GArray *: box_list,                                                      \
      Value *: (Value * (*)(Value *))0,                                        \
      default: (Value * (*)(void *))0)(x)

#define UNBOX(type, v)                                                         \
  _Generic((type){0},                                                          \
      gint64: unbox_int64,                                                     \
      gdouble: unbox_double,                                                   \
      bool: unbox_bool,                                                        \
      GString *: unbox_string,                                                 \
      GArray *: unbox_list)(v)

#endif
