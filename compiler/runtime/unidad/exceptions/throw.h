#ifndef UNIDAD_THROW_H
#define UNIDAD_THROW_H

#include <glib.h>

typedef struct {
  int line;
  int col;
  int end_line;
  int end_col;
} Location;

#define LOC(line, col, end_line, end_col)                                      \
  &(Location) { line, col, end_line, end_col }

extern GHashTable *UNIDAD_MODULE_REGISTRY;

void u_throw(const int code, const Location *span);

#endif
