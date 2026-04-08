#include "../constants.h"
#include "../extern.h"
#include "../libs/sds.h"
#include "../runtime.h"
#include "../types/list.h"
#include "../types/number.h"
#include "../types/str.h"
#include "../units/units.h"
#include "../utils/utils.h"
#include "../values.h"
#include "echo.h"
#include "math_builtins.h"
#include "random_builtins.h"
#include "time_builtins.h"

#include <ctype.h>
#include <glib.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

static Value numerobis_builtin_input(Value *args) {
  if (args[1].type != VALUE_NONE) {
    Value echo_args[] = {EMPTY, args[1], EMPTY_STR};
    echo(echo_args);
    fflush(stdout);
  }

  char *line = NULL;
  size_t n = 0;

  if (getline(&line, &n, stdin) == -1) {
    if (line)
      free(line);
    return str__init__(sdsnew(""));
  }

  // Remove trailing whitespace
  char *end = line + strlen(line) - 1;
  while (end >= line && isspace((unsigned char)*end)) {
    *end = '\0';
    end--;
  }

  Value result = str__init__(sdsnew(line));
  free(line);

  return result;
}

static Value numerobis_builtin_indexof(Value *args) {
  GArray *self = args[2].list;
  Value target = args[1];

  for (unsigned int i = 0; i < self->len; i++) {
    Value item = g_array_index(self, Value, i);
    Value eq_result = __eq__(item, target);

    if (eq_result.boolean) {
      return int__init__((long)i, U_ONE);
    }
  }

  return int__init__(-1L, U_ONE);
}

static Value numerobis_builtin_split(Value *args) {
  sds self = args[2].str;
  sds sep = args[1].type == VALUE_EMPTY ? sdsnew(" ") : args[1].str;

  GArray *result_arr = g_array_new(FALSE, FALSE, sizeof(Value));

  if (sdslen(sep) == 0) {
    const char *p = self;
    const char *end = self + sdslen(self);
    while (p < end) {
      const char *next = utf8_next_char(p, end);
      size_t char_len = (size_t)(next - p);

      sds char_sds = sdsnewlen(p, char_len);
      Value val = str__init__(char_sds);
      g_array_append_val(result_arr, val);

      p = next;
    }
  } else {
    int count;
    sds *parts =
        sdssplitlen(self, (int)sdslen(self), sep, (int)sdslen(sep), &count);

    if (parts) {
      for (int i = 0; i < count; i++) {
        Value val = str__init__(sdsnew(parts[i]));
        g_array_append_val(result_arr, val);
      }
      sdsfreesplitres(parts, count);
    }
  }

  if (args[1].type == VALUE_EMPTY) {
    sdsfree(sep);
  }

  return list__init__(result_arr);
}

static inline Value numerobis_builtin_list_len(Value *args) {
  return int__init__((long)_list_len(args[1].list), U_ONE);
}

static inline Value numerobis_builtin_str_len(Value *args) {
  return int__init__(args[1].str ? _str_len(args[1].str) : 0, U_ONE);
}

static Value numerobis_builtin_exit(Value *args) {
  if (args[2].type != VALUE_EMPTY && args[2].boolean)
    execv(NUMEROBIS__ARGV__[0], NUMEROBIS__ARGV__);
  int exit_code = args[1].type == VALUE_EMPTY ? 0 : (int)_i64(args[1]);
  exit(exit_code);
  return NONE;
}

void u_register_builtin_externs(void) {
  u_extern_register("echo", echo);
  u_extern_register("input", numerobis_builtin_input);
  u_extern_register("List.indexof", numerobis_builtin_indexof);
  u_extern_register("Str.split", numerobis_builtin_split);

  u_extern_register("Str.len", numerobis_builtin_str_len);
  u_extern_register("List.len", numerobis_builtin_list_len);

  u_extern_register("exit", numerobis_builtin_exit);

  numerobis_math_register_builtins();
  numerobis_random_register_builtins();
  numerobis_time_register_builtins();
  numerobis_list_register_externs();
}
