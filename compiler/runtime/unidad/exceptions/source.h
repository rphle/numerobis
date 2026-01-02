#ifndef UNIDAD_SOURCE_H
#define UNIDAD_SOURCE_H

#include <glib.h>

typedef struct {
  const gchar *path;
  const int n_lines;
  const gchar *source[];
} UnidadProgram;

extern const UnidadProgram UNIDAD_PROGRAM;

#endif
