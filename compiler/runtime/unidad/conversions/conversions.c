#include "../exceptions/throw.h"
#include "../types/number.h"
#include "../types/str.h"
#include "../values.h"
#include <glib.h>
#include <stdio.h>

Value *__to_str__(Value *val, const Location *loc) {
  GString *result = g_string_new("");

  switch (val->type) {
  case VALUE_NUMBER: {
    Number *n = val->number;
    if (n->kind == NUM_INT64) {
      g_string_printf(result, "%ld", n->i64);
    } else {
      g_string_printf(result, "%g", n->f64);
    }
    break;
  }

  case VALUE_BOOL:
    g_string_assign(result, val->boolean ? "true" : "false");
    break;

  case VALUE_STR:
    g_string_assign(result, val->str->str);
    break;

  case VALUE_LIST: {
    g_string_append_c(result, '[');
    GArray *arr = val->list;
    for (size_t i = 0; i < arr->len; i++) {
      if (i > 0)
        g_string_append(result, ", ");

      Value *elem = g_array_index(arr, Value *, i);
      if (elem && elem->type == VALUE_STR) {
        g_string_append_printf(result, "\"%s\"", elem->str->str);
      } else {
        // recursively convert
        Value *elem_str = __to_str__(elem, loc);
        g_string_append(result, elem_str->str->str);
      }
    }
    g_string_append_c(result, ']');
    break;
  }

  case VALUE_NONE:
    g_string_assign(result, "None");
    break;

  case VALUE_RANGE:
    g_string_assign(result, "[Range]");
    break;

  default:
    g_string_assign(result, "[Unknown]");
    break;
  }

  return str__init__(result);
}

Value *__to_int__(Value *val, const Location *loc) {
  switch (val->type) {
  case VALUE_NUMBER: {
    Number *n = val->number;
    if (n->kind == NUM_INT64) {
      return int__init__(n->i64);
    } else {
      return int__init__((gint64)n->f64);
    }
  }

  case VALUE_BOOL:
    return int__init__(val->boolean ? 1 : 0);

  case VALUE_STR: {
    const gchar *str = val->str->str;
    gchar *endptr = NULL;

    while (g_ascii_isspace(*str)) {
      str++;
    }

    if (*str == '\0') {
      u_throw(301, loc);
    }

    gint64 result = g_ascii_strtoll(str, &endptr, 10);

    while (g_ascii_isspace(*endptr)) {
      endptr++;
    }

    if (*endptr != '\0') {
      u_throw(301, loc);
    }

    return int__init__(result);
  }

  case VALUE_NONE:
    u_throw(301, loc);

  default:
    u_throw(301, loc);
  }
}
