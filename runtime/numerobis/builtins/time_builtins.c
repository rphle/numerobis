#include "time_builtins.h"
#include "../constants.h"
#include "../extern.h"
#include "../types/number.h"
#include "../units/units.h"
#include "../utils/utils.h"
#include "../values.h"

#include <time.h>

struct timespec ts;

static Value numerobis_builtin_now(Value *args) {
  clock_gettime(CLOCK_REALTIME, &ts);
  double seconds = ts.tv_sec + ts.tv_nsec * 1e-9;
  return num__init__(seconds, U_ONE);
}

static Value numerobis_builtin_sleep(Value *args) {
  double seconds = _f64(args[1]);
  if (seconds <= 0)
    return NONE;

  ts.tv_sec = (time_t)seconds;
  ts.tv_nsec = (long)((seconds - ts.tv_sec) * 1e9);
  nanosleep(&ts, NULL);

  return NONE;
}

void numerobis_time_register_builtins(void) {
  u_extern_register("now", numerobis_builtin_now);
  u_extern_register("sleep", numerobis_builtin_sleep);
}
