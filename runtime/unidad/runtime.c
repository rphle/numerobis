#include "runtime.h"
#include "builtins/builtins.h"
#include "extern.h"

char *UNIDAD__FILE__ = NULL;

__attribute__((constructor)) static void unidad_runtime_ctor(void) {
  GC_INIT();
  u_externs_init();
  u_register_builtin_externs();
}
