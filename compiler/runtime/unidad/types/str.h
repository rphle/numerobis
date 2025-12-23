#ifndef UNIDAD_STR_H
#define UNIDAD_STR_H

#include <glib.h>
#include <stddef.h>

GString *str__getitem__(GString *self, size_t index);
GString *str__getslice__(GString *self, ssize_t start, ssize_t end,
                         ssize_t step);
GString *str__add__(GString *self, GString *other);
GString *str__mul__(GString *self, ssize_t n);

#endif
