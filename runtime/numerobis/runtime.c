#include "runtime.h"
#include "builtins/builtins.h"
#include "extern.h"
#include "types/bool.h"
#include "types/list.h"
#include "types/number.h"
#include "types/range.h"
#include "types/str.h"

int NUMEROBIS__FILE__ = 0;

__attribute__((constructor)) static void numerobis_runtime_ctor(void) {
  GC_INIT();
  u_externs_init();
  u_register_builtin_externs();
  bool_methods_init();
  list_methods_init();
  number_methods_init();
  range_methods_init();
  str_methods_init();
}
