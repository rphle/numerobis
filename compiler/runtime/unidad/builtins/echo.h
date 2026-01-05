#ifndef UNIDAD_ECHO_H
#define UNIDAD_ECHO_H

#include "../values.h"
#include <glib.h>
#include <stdbool.h>
#include <stdio.h>

static __thread bool _echo_in_list = false;

#define echo_dispatch(x)                                                       \
  _Generic((x),                                                                \
      gint64: echo_int64,                                                      \
      gdouble: echo_double,                                                    \
      Number *: echo_number,                                                   \
      GString *: echo_string,                                                  \
      GArray *: echo_garray,                                                   \
      bool: echo_bool,                                                         \
      default: echo_value)(x)

#define echo(x, end)                                                           \
  do {                                                                         \
    echo_dispatch(x);                                                          \
    echo_dispatch(end);                                                        \
  } while (0)

/* ---------- declarations ---------- */
static inline void echo_value(gpointer v);
static inline void echo_number(Number *n);
static inline void echo_garray(GArray *arr);

/* ------------------------------------------ */
static inline void echo_int64(gint64 x) { g_print("%d", x); }
static inline void echo_double(double x) { g_print("%g", x); }
static inline void echo_string(GString *x) {
  if (_echo_in_list)
    g_print("\"%s\"", x->str);
  else
    g_print("%s", x->str);
}
static inline void echo_bool(bool x) { g_print("%s", x ? "true" : "false"); }
static inline void echo_ptr(const void *x) { g_print("[unsupported: %p]", x); }

static inline void echo_value(gpointer v) {
  if (!v) {
    g_print("null");
    return;
  }
  Value *val = (Value *)v;
  switch (val->type) {
  case VALUE_NUMBER:
    echo_number(val->number);
    return;
  case VALUE_STR:
    echo_string(val->str);
    return;
  case VALUE_BOOL:
    echo_bool(val->boolean);
    return;
  case VALUE_LIST:
    echo_garray(val->list);
    return;
  case VALUE_NONE:
    g_print("None");
    return;
  }
  echo_ptr(v);
}

static inline void echo_number(Number *n) {
  switch (n->kind) {
  case NUM_INT64:
    echo_int64(n->i64);
    break;
  case NUM_DOUBLE:
    echo_double(n->f64);
    break;
  }
}

static inline void echo_garray(GArray *arr) {
  if (!arr) {
    g_print("[]");
    return;
  }
  bool was_in_list = _echo_in_list;
  _echo_in_list = true;

  g_print("[");
  for (size_t i = 0; i < arr->len; i++) {
    if (i > 0)
      g_print(", ");
    gpointer elem = g_array_index(arr, gpointer, i);
    echo_dispatch(elem);
  }
  g_print("]");

  _echo_in_list = was_in_list;
}

#endif
