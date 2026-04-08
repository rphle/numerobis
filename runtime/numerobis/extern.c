#include "extern.h"
#include <gc.h>
#include <glib.h>
#include <stdio.h>
#include <stdlib.h>

GHashTable *NUMEROBIS_EXTERNS = NULL;

void u_externs_init(void) {
  NUMEROBIS_EXTERNS =
      g_hash_table_new_full(g_str_hash, g_str_equal, NULL, u_extern_entry_free);
}

void u_externs_shutdown(void) {
  if (NUMEROBIS_EXTERNS) {
    g_hash_table_destroy(NUMEROBIS_EXTERNS);
    NUMEROBIS_EXTERNS = NULL;
  }
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
  if (!name || !fn || !NUMEROBIS_EXTERNS)
    return;

  char *key = GC_STRDUP(name);

  if (g_hash_table_contains(NUMEROBIS_EXTERNS, key)) {
    fprintf(stderr, "Extern function already defined: %s\n", name);
    exit(1);
  }

  UExternEntry *e = GC_MALLOC(sizeof(UExternEntry));
  e->name = key;
  e->fn = extern_fn__init__(fn);

  g_hash_table_insert(NUMEROBIS_EXTERNS, key, e);
}

Value *u_extern_lookup(const char *name) {
  UExternEntry *e = g_hash_table_lookup(NUMEROBIS_EXTERNS, name);
  if (e)
    return e->fn;

  fprintf(stderr, "Extern function not found: %s\n", name);
  exit(1);
  return NULL;
}
