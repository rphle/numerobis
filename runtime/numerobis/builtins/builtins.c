#include "../constants.h"
#include "../extern.h"
#include "../types/list.h"
#include "../types/number.h"
#include "../types/str.h"
#include "../units/units.h"
#include "../utils/utils.h"
#include "../values.h"
#include "echo.h"
#include "math_builtins.h"
#include "time_builtins.h"

#include <glib.h>
#include <stdio.h>
#include <stdlib.h>

static Value numerobis_builtin_input(Value *args) {
  if (args[1].type != VALUE_NONE) {
    Value echo_args[] = {NONE, args[1], EMPTY_STR};
    echo(echo_args);
    fflush(stdout);
  }

  gchar *line = NULL;
  size_t n = 0;

  if (getline((char **)&line, &n, stdin) == -1) {
    if (line)
      free(line);
    return str__init__(g_string_new(""));
  }

  g_strchomp(line);

  Value result = str__init__(g_string_new(line));
  free(line);

  return result;
}

static Value numerobis_builtin_indexof(Value *args) {
  GArray *self = args[1].list;
  Value target = args[2];

  for (guint i = 0; i < self->len; i++) {
    Value *item = g_array_index(self, Value *, i);
    Value eq_result = __eq__(*item, target);

    if (eq_result.boolean) {
      return int__init__((gint64)i, U_ONE);
    }
  }

  return int__init__(G_GINT64_CONSTANT(-1), U_ONE);
}

static Value numerobis_builtin_split(Value *args) {
  GString *self = args[1].str;
  GString *sep = args[2].str;

  GArray *result_arr = g_array_new(FALSE, FALSE, sizeof(Value *));

  if (sep->len == 0) {
    const char *p = self->str;
    while (*p) {
      const char *next = g_utf8_next_char(p);
      gssize char_len = next - p;

      GString *char_str = g_string_new_len(p, char_len);
      Value *val = g_new(Value, 1);
      *val = str__init__(char_str);
      g_array_append_val(result_arr, val);

      p = next;
    }
  } else {
    gchar **parts = g_strsplit(self->str, sep->str, -1);

    if (parts) {
      for (int i = 0; parts[i] != NULL; i++) {
        Value *val = g_new(Value, 1);
        *val = str__init__(g_string_new(parts[i]));
        g_array_append_val(result_arr, val);
      }
      g_strfreev(parts);
    }
  }

  return list__init__(result_arr);
}

static inline Value numerobis_builtin_list_len(Value *args) {
  return int__init__((gint64)_list_len(args[1].list), U_ONE);
}

static inline Value numerobis_builtin_str_len(Value *args) {
  return int__init__(args[1].str ? _str_len(args[1].str) : 0, U_ONE);
}

static Value numerobis_builtin_exit(Value *args) {
  int exit_code = args[1].type == VALUE_NONE ? 0 : _i64(args[1]);
  exit(exit_code);
  return NONE;
}

void u_register_builtin_externs(void) {
  u_extern_register("echo", echo);
  u_extern_register("input", numerobis_builtin_input);
  u_extern_register("indexof", numerobis_builtin_indexof);
  u_extern_register("split", numerobis_builtin_split);
  u_extern_register("Str_dlen", numerobis_builtin_str_len);
  u_extern_register("List_dlen", numerobis_builtin_list_len);
  u_extern_register("exit", numerobis_builtin_exit);

  numerobis_math_register_builtins();
  numerobis_time_register_builtins();
}
