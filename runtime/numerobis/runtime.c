#include "runtime.h"
#include "builtins/builtins.h"
#include "extern.h"

char *NUMEROBIS__FILE__ = NULL;

__attribute__((constructor)) static void numerobis_runtime_ctor(void) {
  GC_INIT();
  u_externs_init();
  u_register_builtin_externs();
}
