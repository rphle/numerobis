#ifndef UNIDAD_STR_H
#define UNIDAD_STR_H

#include <glib.h>
#include <stddef.h>

GString *str__getitem__(GString *self, size_t index);
GString *str__getslice__(GString *self, size_t start, size_t end);

#endif
