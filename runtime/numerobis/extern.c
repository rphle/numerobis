#include "extern.h"
#include "libs/gc_stb_ds.h"

#include "libs/bdwgc/include/gc.h"
#include <stdio.h>
#include <stdlib.h>

ExternEntry *NUMEROBIS_EXTERNS = NULL;

void u_externs_shutdown(void) {
  shfree(NUMEROBIS_EXTERNS);
  NUMEROBIS_EXTERNS = NULL;
}

Value *extern_fn__init__(Value (*fn)(Value *args)) {
  Value *v = GC_MALLOC(sizeof(Value));
  v->type = VALUE_EXTERN_FN;
  v->extern_fn = fn;
  return v;
}

void u_extern_register(const char *name, Value (*fn)(Value *args)) {
  if (!name || !fn)
    return;
  if (shgetp_null(NUMEROBIS_EXTERNS, name) != NULL) {
    fprintf(stderr, "Extern function already defined: %s\n", name);
    exit(1);
  }
  shput(NUMEROBIS_EXTERNS, GC_STRDUP(name), extern_fn__init__(fn));
}

Value *u_extern_lookup(const char *name) {
  ExternEntry *entry = shgetp_null(NUMEROBIS_EXTERNS, name);
  if (entry)
    return entry->value;

  fprintf(stderr, "Extern function not found: %s\n", name);
  exit(1);
  return NULL;
}
