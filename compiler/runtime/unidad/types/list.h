#ifndef UNIDAD_LIST_H
#define UNIDAD_LIST_H

#include <glib.h>
#include <stdbool.h>
#include <stddef.h>

GArray *list_of(gpointer first, ...) ;

size_t list_len(const GArray *self);

gpointer list__getitem__(GArray *self, ssize_t index);
GArray *list__getslice__(GArray *self, ssize_t start, ssize_t end,
                         ssize_t step);

GArray *list__add__(GArray *self, GArray *other);
GArray *list__mul__(GArray *self, ssize_t n);

bool list__bool__(GArray *self);

bool list__lt__(GArray *self, GArray *other);
bool list__le__(GArray *self, GArray *other);
bool list__gt__(GArray *self, GArray *other);
bool list__ge__(GArray *self, GArray *other);

bool list__eq__(const GArray *a, const GArray *b);

#endif
