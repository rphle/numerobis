#ifndef NUMEROBIS_SOURCE_H
#define NUMEROBIS_SOURCE_H

#include <glib.h>

typedef struct {
  const char *path;
  const int n_lines;
  const char **source;
} NumerobisProgram;

extern GHashTable *NUMEROBIS_MODULE_REGISTRY;

#endif
