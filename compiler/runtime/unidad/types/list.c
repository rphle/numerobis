#include "list.h"
#include "../utils/utils.h"
#include <glib.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

size_t list_len(const GArray *self) {
  return self ? self->len : 0;
}

/* Create a list from a variable number of gpointer arguments, ending with NULL
 */
GArray *list_of(gpointer first, ...) {
  GArray *result = g_array_new(FALSE, FALSE, sizeof(gpointer));

  if (!first)
    return result;

  va_list ap;
  va_start(ap, first);

  gpointer current = first;
  while (current) {
    g_array_append_val(result, current);
    current = va_arg(ap, gpointer);
  }

  va_end(ap);
  return result;
}

gpointer list__getitem__(GArray *self, ssize_t index) {
  ssize_t len = (ssize_t)list_len(self);
  if (len == 0)
    return NULL;

  ssize_t nidx = normalize_index(index, len);
  if (nidx < 0 || nidx >= len)
    return NULL;

  return g_array_index(self, gpointer, (guint)nidx);
}

GArray *list__getslice__(GArray *self, ssize_t start, ssize_t end,
                         ssize_t step) {
  ssize_t len = (ssize_t)list_len(self);
  GArray *result = g_array_new(FALSE, FALSE, sizeof(gpointer));

  if (len == 0 || step == 0)
    return result;

  normalize_slice(len, &start, &end, &step);

  for (ssize_t i = start; step > 0 ? i < end : i > end; i += step) {
    gpointer val = g_array_index(self, gpointer, (guint)i);
    g_array_append_val(result, val);
  }

  return result;
}

GArray *list__add__(GArray *self, GArray *other) {
  size_t a_len = list_len(self);
  size_t b_len = list_len(other);
  GArray *result =
      g_array_sized_new(FALSE, FALSE, sizeof(gpointer), (guint)(a_len + b_len));

  for (guint i = 0; i < (guint)a_len; i++) {
    gpointer val = g_array_index(self, gpointer, i);
    g_array_append_val(result, val);
  }

  for (guint i = 0; i < (guint)b_len; i++) {
    gpointer val = g_array_index(other, gpointer, i);
    g_array_append_val(result, val);
  }

  return result;
}

GArray *list__mul__(GArray *self, ssize_t n) {
  size_t len = list_len(self);
  if (n <= 0 || len == 0)
    return g_array_new(FALSE, FALSE, sizeof(gpointer));

  /* Guard overflow when computing capacity */
  unsigned long long total = (unsigned long long)len * (unsigned long long)n;
  guint reserve = (total > G_MAXUINT) ? G_MAXUINT : (guint)total;
  GArray *result = g_array_sized_new(FALSE, FALSE, sizeof(gpointer), reserve);

  for (ssize_t r = 0; r < n; r++) {
    for (guint i = 0; i < (guint)len; i++) {
      gpointer val = g_array_index(self, gpointer, i);
      g_array_append_val(result, val);
    }
  }

  return result;
}

void list_append(GArray *self, gpointer val) {
  if (self)
    g_array_append_val(self, val);
}

void list_extend(GArray *self, GArray *other) {
  if (!self || !other)
    return;
  for (guint i = 0; i < other->len; i++) {
    gpointer val = g_array_index(other, gpointer, i);
    g_array_append_val(self, val);
  }
}

void list_insert(GArray *self, ssize_t index, gpointer val) {
  if (!self)
    return;

  ssize_t len = (ssize_t)self->len;
  index = normalize_index(index, len);

  if (index <= 0)
    g_array_insert_val(self, 0, val);
  else if (index >= len)
    g_array_append_val(self, val);
  else
    g_array_insert_val(self, (guint)index, val);
}

bool list__setitem__(GArray *self, ssize_t index, gpointer val) {
  if (!self)
    return false;

  ssize_t len = (ssize_t)self->len;
  ssize_t nidx = normalize_index(index, len);
  if (nidx < 0 || nidx >= len)
    return false;

  g_array_index(self, gpointer, (guint)nidx) = val;
  return true;
}

bool list__delitem__(GArray *self, ssize_t index) {
  if (!self)
    return false;

  ssize_t len = (ssize_t)self->len;
  ssize_t nidx = normalize_index(index, len);
  if (nidx < 0 || nidx >= len)
    return false;

  g_array_remove_index(self, (guint)nidx);
  return true;
}

gpointer list_pop(GArray *self, ssize_t index, bool has_index) {
  if (!self || self->len == 0)
    return NULL;

  ssize_t len = (ssize_t)self->len;
  ssize_t idx = has_index ? index : len - 1;
  ssize_t nidx = normalize_index(idx, len);

  if (nidx < 0 || nidx >= len)
    return NULL;

  gpointer val = g_array_index(self, gpointer, (guint)nidx);
  g_array_remove_index(self, (guint)nidx);
  return val;
}

bool list__bool__(GArray *self) { return list_len(self) > 0; }

/* Shallow equality: pointer-equality of elements and equal length. */
bool list__eq__(const GArray *a, const GArray *b) {
  if (a == b)
    return true;
  if (!a || !b || a->len != b->len)
    return false;

  for (guint i = 0; i < a->len; i++) {
    if (g_array_index((GArray *)a, gpointer, i) !=
        g_array_index((GArray *)b, gpointer, i))
      return false;
  }

  return true;
}

bool list__lt__(GArray *self, GArray *other) {
  return list_len(self) < list_len(other);
}

bool list__le__(GArray *self, GArray *other) {
  return list_len(self) <= list_len(other);
}

bool list__gt__(GArray *self, GArray *other) {
  return list_len(self) > list_len(other);
}

bool list__ge__(GArray *self, GArray *other) {
  return list_len(self) >= list_len(other);
}
