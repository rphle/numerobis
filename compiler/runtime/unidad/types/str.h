#ifndef UNIDAD_STR_H
#define UNIDAD_STR_H

#include <glib.h>
#include <stdbool.h>
#include <stddef.h>

size_t str_len(const GString *self);

GString *str__getitem__(GString *self, size_t index);
GString *str__getslice__(GString *self, ssize_t start, ssize_t end,
                         ssize_t step);
GString *str__add__(GString *self, GString *other);
GString *str__mul__(GString *self, ssize_t n);

bool str__lt__(GString *self, GString *other);
bool str__le__(GString *self, GString *other);
bool str__gt__(GString *self, GString *other);
bool str__ge__(GString *self, GString *other);

bool str__eq__(const GString *a, const GString *b);

#endif
