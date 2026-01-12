#include "../extern.h"
#include "../types/list.h"
#include "../types/number.h"
#include "../types/str.h"
#include "../values.h"
#include "echo.h"
#include <glib.h>
#include <math.h>
#include <stdio.h>

static Value *unidad_builtin_random(Value **args) {
  static GRand *rng = NULL;

  if (G_UNLIKELY(rng == NULL)) {
    rng = g_rand_new();
  }

  double x = g_rand_double(rng);

  return float__init__(x);
}

static Value *unidad_builtin_input(Value **args) {
  if (args[1]) {
    echo((Value *[]){NULL, args[1], EMPTY_STR});
    fflush(stdout);
  }

  gchar *line = NULL;
  size_t n = 0;

  if (getline((char **)&line, &n, stdin) == -1) {
    return str__init__(g_string_new(""));
  }

  g_strchomp(line);

  Value *result = str__init__(g_string_new(line));

  return result;
}

static Value *unidad_builtin_floor(Value **args) {

  Value *val = args[1];

  Number *n = val->number;
  gint64 result;

  if (n->kind == NUM_INT64) {
    result = n->i64;
  } else {
    result = (gint64)floor(n->f64);
  }

  return int__init__(result);
}

static Value *unidad_builtin_indexof(Value **args) {
  GArray *self = args[1]->list;
  Value *target = args[2];

  for (guint i = 0; i < self->len; i++) {
    Value *item = g_array_index(self, Value *, i);
    Value *eq_result = __eq__(item, target);

    if (eq_result->boolean) {
      return int__init__((gint64)i);
    }
  }

  return int__init__(G_GINT64_CONSTANT(-1));
}

static Value *unidad_builtin_split(Value **args) {
  GString *self = args[1]->str;
  GString *sep = args[2]->str;

  GArray *result_arr = g_array_new(FALSE, FALSE, sizeof(Value *));

  if (sep->len == 0) {
    const char *p = self->str;
    while (*p) {
      const char *next = g_utf8_next_char(p);
      gssize char_len = next - p;

      GString *char_str = g_string_new_len(p, char_len);
      Value *val = str__init__(char_str);
      g_array_append_val(result_arr, val);

      p = next;
    }
  } else {
    gchar **parts = g_strsplit(self->str, sep->str, -1);

    if (parts) {
      for (int i = 0; parts[i] != NULL; i++) {
        Value *val = str__init__(g_string_new(parts[i]));
        g_array_append_val(result_arr, val);
      }
    }
  }

  return list__init__(result_arr);
}

void u_register_builtin_externs(void) {
  u_extern_register("echo", echo);
  u_extern_register("random", unidad_builtin_random);
  u_extern_register("input", unidad_builtin_input);
  u_extern_register("floor", unidad_builtin_floor);
  u_extern_register("indexof", unidad_builtin_indexof);
  u_extern_register("split", unidad_builtin_split);
}
