#include "echo.h"
#include "../constants.h"
#include "../types/str.h"
#include "../values.h"
#include <glib.h>
#include <stdbool.h>
#include <stdio.h>

static __thread bool _echo_in_list = false;

static inline void echo_number(Number *n) {
  switch (n->kind) {
  case NUM_INT64:
    g_print("%d", n->i64);
    break;
  case NUM_DOUBLE:
    g_print("%g", n->f64);
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
    echo((Value *[]){NULL, elem, EMPTY_STR});
  }
  g_print("]");

  _echo_in_list = was_in_list;
}

Value *echo(Value **args) {
  Value *val = args[1];
  Value *end = args[2];

  switch (val->type) {
  case VALUE_NUMBER:
    echo_number(val->number);
    break;
  case VALUE_STR:
    if (_echo_in_list)
      g_print("\"%s\"", val->str->str);
    else
      g_print("%s", val->str->str);
    break;
  case VALUE_BOOL:
    g_print("%s", val->boolean ? "true" : "false");
    break;
  case VALUE_LIST:
    echo_garray(val->list);
    break;
  case VALUE_RANGE:
    g_print("<Range %p>", val->range);
    break;
  case VALUE_CLOSURE:
    g_print("<Function %p>", val->closure);
    break;
  case VALUE_EXTERN_FN:
    g_print("<Extern Function %p>", val->extern_fn);
    break;
  case VALUE_NONE:
    g_print("None");
    break;
  }

  if (end && end->type == VALUE_STR) {
    g_print("%s", end->str->str);
  } else {
    g_print("\n");
  }

  return NONE;
}
