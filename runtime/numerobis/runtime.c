#include "runtime.h"
#include "builtins/builtins.h"
#include "extern.h"

int NUMEROBIS__FILE__ = 0;

__attribute__((constructor)) static void numerobis_runtime_ctor(void) {
  GC_INIT();
  u_externs_init();
  u_register_builtin_externs();
}
