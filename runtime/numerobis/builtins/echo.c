#include "echo.h"
#include "../constants.h"
#include "../types/str.h"
#include "../types/struct.h"
#include "../units/eval.h"
#include "../values.h"
#include <glib.h>
#include <stdbool.h>
#include <stdio.h>

static __thread bool _echo_in_list = false;

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
    Value elem = g_array_index(arr, Value, i);
    Value args[] = {EMPTY, elem, EMPTY_STR};
    echo(args);
  }
  g_print("]");

  _echo_in_list = was_in_list;
}

Value echo(Value *args) {
  Value val = args[1];
  Value end = args[2];

  if (val.type == VALUE_NONE) {
    val = EMPTY_STR;
  }

  switch (val.type) {
  case VALUE_NUMBER:
    g_print("%s", print_number(&val.number)->str);
    break;
  case VALUE_STR:
    if (_echo_in_list)
      g_print("\"%s\"", val.str->str);
    else
      g_print("%s", val.str->str);
    break;
  case VALUE_BOOL:
    g_print("%s", val.boolean ? "true" : "false");
    break;
  case VALUE_LIST:
    echo_garray(val.list);
    break;
  case VALUE_RANGE:
    g_print("<Range %p>", val.range);
    break;
  case VALUE_CLOSURE:
    g_print("<Function %p>", val.closure);
    break;
  case VALUE_EXTERN_FN:
    g_print("<Extern Function %p>", val.extern_fn);
    break;
  case VALUE_STRUCT:
    g_print("%s", struct__cstr__(val)->str);
    break;
  case VALUE_NONE:
  case VALUE_EMPTY:
    g_print("None");
    break;
  }

  if (end.type == VALUE_STR) {
    g_print("%s", end.str->str);
  } else {
    g_print("\n");
  }

  return NONE;
}
