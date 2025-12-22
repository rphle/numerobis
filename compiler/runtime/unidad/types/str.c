#include "../constants.h"
#include <glib.h>
#include <stddef.h>

static size_t gstring_len(GString *self) {
  return g_utf8_strlen(self->str, self->len);
}

GString *str__getitem__(GString *self, ssize_t index) {
  size_t len = gstring_len(self);

  // Handle negative index like Python
  if (index < 0)
    index += len;

  if (index < 0 || (size_t)index >= len)
    return g_string_new(""); // out of bounds

  const char *p = self->str;
  for (size_t i = 0; i < (size_t)index; i++)
    p = g_utf8_next_char(p);

  gunichar ch = g_utf8_get_char(p);

  gchar buf[8];
  gint len_utf8 = g_unichar_to_utf8(ch, buf);
  buf[len_utf8] = '\0';

  return g_string_new(buf);
}

GString *str__getslice__(GString *self, ssize_t start, ssize_t end,
                         ssize_t step) {
  ssize_t len = (ssize_t)gstring_len(self);

  if (step == 0)
    return g_string_new("");

  if (start == SLICE_NONE)
    start = (step < 0) ? len - 1 : 0;
  if (end == SLICE_NONE)
    end = (step < 0) ? -len - 1 : len;

  // Handle negative indices
  if (start < 0)
    start += len;
  if (end < 0)
    end += len;

  // Clamp to bounds
  if (start < 0)
    start = (step < 0) ? -1 : 0;
  if (start > len)
    start = len;
  if (end < 0)
    end = (step < 0) ? -1 : 0;
  if (end > len)
    end = len;

  // Build array of character positions
  const char *str_end = self->str + self->len;
  const char **positions = g_malloc((len + 1) * sizeof(char *));
  const char *p = self->str;
  size_t pos_idx = 0;

  while (p < str_end) {
    positions[pos_idx++] = p;
    p = g_utf8_next_char(p);
  }
  positions[pos_idx] = str_end; // Mark the end

  GString *result = g_string_new("");

  for (ssize_t i = start; step > 0 ? i < end : i > end; i += step) {
    if (i >= 0 && i < len) {
      const char *char_start = positions[i];
      const char *char_end = positions[i + 1];
      g_string_append_len(result, char_start, char_end - char_start);
    }
  }

  g_free(positions);
  return result;
}

GString *str__add__(GString *self, GString *other) {
  GString *result = g_string_sized_new(self->len + other->len);
  g_string_append_len(result, self->str, self->len);
  g_string_append_len(result, other->str, other->len);
  return result;
}

GString *str__mul__(GString *self, ssize_t n) {
  if (n <= 0)
    return g_string_new("");
  GString *result = g_string_sized_new(self->len * n);
  for (ssize_t i = 0; i < n; i++)
    g_string_append_len(result, self->str, self->len);
  return result;
}
