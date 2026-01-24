#include "extern.h"

GHashTable *UNIDAD_EXTERNS = NULL;

void u_externs_init(void) {
  UNIDAD_EXTERNS =
      g_hash_table_new_full(g_str_hash, g_str_equal, g_free, g_free);
}

Value *extern_fn__init__(Value *(*fn)(Value **args)) {
  Value *v = g_new(Value, 1);
  v->type = VALUE_EXTERN_FN;
  v->extern_fn = fn;
  v->methods = NULL;
  return v;
}

void u_extern_register(const char *name, Value *(*fn)(Value **args)) {
  g_return_if_fail(name != NULL);
  g_return_if_fail(fn != NULL);
  g_return_if_fail(UNIDAD_EXTERNS != NULL);

  char *key = g_strdup(name);

  if (g_hash_table_contains(UNIDAD_EXTERNS, key)) {
    g_free(key);
    g_error("Extern function already defined: %s", name);
  }

  UExternEntry *e = g_new(UExternEntry, 1);
  e->name = key;
  e->fn = extern_fn__init__(fn);

  g_hash_table_insert(UNIDAD_EXTERNS, key, e);
}

Value *u_extern_lookup(const char *name) {
  UExternEntry *e = g_hash_table_lookup(UNIDAD_EXTERNS, name);
  return e ? e->fn : NULL;
}
