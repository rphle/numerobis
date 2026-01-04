#include "runtime.h"
#include "builtins/builtins.h"
#include "extern.h"

__attribute__((constructor)) static void unidad_runtime_ctor(void) {
  GC_INIT();
  u_extern_init();
  u_register_builtin_externs();
}
