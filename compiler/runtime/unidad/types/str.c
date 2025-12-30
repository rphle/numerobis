#include "../utils/utils.h"
#include <glib.h>
#include <stdbool.h>
#include <stddef.h>

size_t str_len(const GString *self) {
  return self ? g_utf8_strlen(self->str, self->len) : 0;
}

static const char **build_char_positions(const GString *self, size_t len) {
  const char **positions = g_malloc((len + 1) * sizeof(char *));
  const char *p = self->str;
  const char *end = self->str + self->len;

  for (size_t i = 0; i < len && p < end; i++) {
    positions[i] = p;
    p = g_utf8_next_char(p);
  }
  positions[len] = end;

  return positions;
}

bool str__bool__(GString *self) { return self->len > 0; };

GString *str__getitem__(GString *self, ssize_t index) {
  if (!self)
    return g_string_new("");

  ssize_t len = (ssize_t)str_len(self);
  ssize_t nidx = normalize_index(index, len);

  if (nidx < 0 || nidx >= len)
    return g_string_new("");

  const char *p = self->str;
  for (ssize_t i = 0; i < nidx; i++)
    p = g_utf8_next_char(p);

  gunichar ch = g_utf8_get_char(p);
  gchar buf[8];
  gint utf8_len = g_unichar_to_utf8(ch, buf);
  buf[utf8_len] = '\0';

  return g_string_new(buf);
}

GString *str__getslice__(GString *self, ssize_t start, ssize_t end,
                         ssize_t step) {
  if (!self)
    return g_string_new("");

  ssize_t len = (ssize_t)str_len(self);
  if (len == 0 || step == 0)
    return g_string_new("");

  normalize_slice(len, &start, &end, &step);

  if ((step > 0 && start >= end) || (step < 0 && start <= end))
    return g_string_new("");

  const char **positions = build_char_positions(self, len);
  GString *result = g_string_new("");

  for (ssize_t i = start; step > 0 ? i < end : i > end; i += step) {
    if (i >= 0 && i < len) {
      g_string_append_len(result, positions[i],
                          positions[i + 1] - positions[i]);
    }
  }

  g_free(positions);
  return result;
}

GString *str__add__(GString *self, GString *other) {
  if (!self || !other)
    return g_string_new("");

  GString *result = g_string_sized_new(self->len + other->len);
  g_string_append_len(result, self->str, self->len);
  g_string_append_len(result, other->str, other->len);
  return result;
}

GString *str__mul__(GString *self, ssize_t n) {
  if (!self || n <= 0)
    return g_string_new("");

  /* Guard overflow */
  unsigned long long total =
      (unsigned long long)self->len * (unsigned long long)n;
  size_t capacity = (total > G_MAXUINT) ? G_MAXUINT : (size_t)total;

  GString *result = g_string_sized_new(capacity);
  for (ssize_t i = 0; i < n; i++)
    g_string_append_len(result, self->str, self->len);

  return result;
}

bool str__eq__(const GString *a, const GString *b) {
  if (a == b)
    return true;
  if (!a || !b)
    return false;
  return g_string_equal(a, b);
}

bool str__lt__(GString *self, GString *other) {
  if (!self || !other)
    return false;
  return strcmp(self->str, other->str) < 0;
}

bool str__le__(GString *self, GString *other) {
  if (!self || !other)
    return false;
  return strcmp(self->str, other->str) <= 0;
}

bool str__gt__(GString *self, GString *other) {
  if (!self || !other)
    return false;
  return strcmp(self->str, other->str) > 0;
}

bool str__ge__(GString *self, GString *other) {
  if (!self || !other)
    return false;
  return strcmp(self->str, other->str) >= 0;
}
