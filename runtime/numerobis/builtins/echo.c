#include "echo.h"
#include "../constants.h"
#include "../libs/sds.h"
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
    printf("[]");
    return;
  }
  bool was_in_list = _echo_in_list;
  _echo_in_list = true;

  printf("[");
  for (size_t i = 0; i < arr->len; i++) {
    if (i > 0)
      printf(", ");
    Value elem = g_array_index(arr, Value, i);
    Value args[] = {EMPTY, elem, EMPTY_STR};
    echo(args);
  }
  printf("]");

  _echo_in_list = was_in_list;
}

Value echo(Value *args) {
  Value val = args[1];
  Value end = args[2];

  if (val.type == VALUE_NONE) {
    val = EMPTY_STR;
  }

  switch (val.type) {
  case VALUE_NUMBER: {
    sds num_str = print_number(&val.number);
    printf("%s", num_str);
    break;
  }
  case VALUE_STR:
    if (_echo_in_list)
      printf("\"%s\"", val.str);
    else
      printf("%s", val.str);
    break;
  case VALUE_BOOL:
    printf("%s", val.boolean ? "true" : "false");
    break;
  case VALUE_LIST:
    echo_garray(val.list);
    break;
  case VALUE_RANGE:
    printf("<Range %p>", (void *)val.range);
    break;
  case VALUE_CLOSURE:
    printf("<Function %p>", (void *)val.closure);
    break;
  case VALUE_EXTERN_FN:
    printf("<Extern Function %p>", (void *)val.extern_fn);
    break;
  case VALUE_STRUCT: {
    sds struct_str = struct__cstr__(val);
    printf("%s", struct_str);
    sdsfree(struct_str);
    break;
  }
  case VALUE_NONE:
  case VALUE_EMPTY:
    printf("None");
    break;
  }

  if (end.type == VALUE_STR) {
    printf("%s", end.str);
  } else {
    printf("\n");
  }

  return NONE;
}
