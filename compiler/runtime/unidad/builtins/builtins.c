#include "../extern.h"
#include "../types/number.h"
#include "../types/str.h"
#include "../values.h"
#include "echo.h"
#include <glib.h>
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
  if (args[0]) {
    echo_dispatch(args[0]);
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

void u_register_builtin_externs(void) {
  u_extern_register("random", unidad_builtin_random);
  u_extern_register("input", unidad_builtin_input);
}
