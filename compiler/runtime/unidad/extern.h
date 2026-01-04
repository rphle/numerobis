#ifndef UNIDAD_EXTERN_H
#define UNIDAD_EXTERN_H

#include "values.h"
#include <glib.h>

typedef Value *(*UExternFn)(Value **args);

typedef struct {
  const char *name;
  UExternFn fn;
} UExternEntry;

extern GHashTable *UNIDAD_EXTERNS;

void u_extern_init(void);
void u_extern_register(const char *name, UExternFn fn);
UExternFn u_extern_lookup(const char *name);

#endif
