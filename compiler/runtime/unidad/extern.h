#ifndef UNIDAD_EXTERN_H
#define UNIDAD_EXTERN_H

#include "values.h"
#include <glib.h>

typedef struct {
  const char *name;
  Value *fn;
} UExternEntry;

extern GHashTable *UNIDAD_EXTERNS;

void u_externs_init(void);

Value *extern_fn__init__(Value *(*fn)(Value **args));
void u_extern_register(const char *name, Value *(*fn)(Value **args));
Value *u_extern_lookup(const char *name);

#endif
