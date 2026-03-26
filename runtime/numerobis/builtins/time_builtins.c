#include "time_builtins.h"
#include "../constants.h"
#include "../extern.h"
#include "../types/number.h"
#include "../units/units.h"
#include "../utils/utils.h"
#include "../values.h"

#include <glib.h>

static Value numerobis_builtin_now(Value *args) {
  gint64 microseconds = g_get_real_time();
  gdouble seconds = (gdouble)microseconds / 1000000.0;
  return float__init__(seconds, U_ONE);
}

static Value numerobis_builtin_sleep(Value *args) {
  double seconds = _f64(args, 1);
  if (seconds > 0) {
    g_usleep((gulong)(seconds * 1000000));
  }
  return NONE;
}

void numerobis_time_register_builtins(void) {
  u_extern_register("now", numerobis_builtin_now);
  u_extern_register("sleep", numerobis_builtin_sleep);
}
