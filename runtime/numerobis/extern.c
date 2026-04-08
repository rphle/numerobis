#include "extern.h"
#include <gc.h>

GHashTable *NUMEROBIS_EXTERNS = NULL;

void u_externs_init(void) {
  NUMEROBIS_EXTERNS =
      g_hash_table_new_full(g_str_hash, g_str_equal, NULL, u_extern_entry_free);
}

void u_externs_shutdown(void) {
  g_hash_table_destroy(NUMEROBIS_EXTERNS);
  NUMEROBIS_EXTERNS = NULL;
}

Value *extern_fn__init__(Value (*fn)(Value *args)) {
  Value *v = GC_MALLOC(sizeof(Value));
  v->type = VALUE_EXTERN_FN;
  v->extern_fn = fn;
  return v;
}

void u_extern_entry_free(void *data) {
  if (data) {
    UExternEntry *e = (UExternEntry *)data;
    GC_FREE(e);
  }
}

void u_extern_register(const char *name, Value (*fn)(Value *args)) {
  g_return_if_fail(name != NULL);
  g_return_if_fail(fn != NULL);
  g_return_if_fail(NUMEROBIS_EXTERNS != NULL);

  char *key = GC_STRDUP(name);

  if (g_hash_table_contains(NUMEROBIS_EXTERNS, key)) {
    g_error("Extern function already defined: %s", name);
  }

  UExternEntry *e = GC_MALLOC(sizeof(UExternEntry));
  e->name = key;
  e->fn = extern_fn__init__(fn);

  g_hash_table_insert(NUMEROBIS_EXTERNS, key, e);
}

Value *u_extern_lookup(const char *name) {
  UExternEntry *e = g_hash_table_lookup(NUMEROBIS_EXTERNS, name);
  if (e) {
    return e->fn;
  }
  g_error("Extern function not found: %s", name);
  exit(1);
  return NULL;
}
