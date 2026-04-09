#ifndef NUMEROBIS_EXTERN_H
#define NUMEROBIS_EXTERN_H

#include "values.h"
#include <glib.h>

typedef struct {
  char *key;
  Value *value;
} ExternEntry;

extern ExternEntry *NUMEROBIS_EXTERNS;

void u_externs_shutdown(void);

Value *extern_fn__init__(Value (*fn)(Value *args));
void u_extern_entry_free(void *data);
void u_extern_register(const char *name, Value (*fn)(Value *args));
Value *u_extern_lookup(const char *name);

#endif
