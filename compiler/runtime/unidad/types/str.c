#include "../constants.h"
#include <glib.h>
#include <stddef.h>

static size_t gstring_len(GString *self) {
  const char *p = self->str;
  size_t len = 0;
  while (*p) {
    len++;
    p = g_utf8_next_char(p);
  }
  return len;
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

GString *str__getslice__(GString *self, ssize_t start, ssize_t end) {
  size_t len = gstring_len(self);

  if (start == SLICE_NONE)
    start = 0;
  if (end == SLICE_NONE)
    end = len;

  // Handle negative indices
  if (start < 0)
    start += len;
  if (end < 0)
    end += len;

  // Clamp to bounds
  if (start < 0)
    start = 0;
  if (end > (ssize_t)len)
    end = len;
  if (start >= end)
    return g_string_new("");

  const char *p = self->str;
  const char *begin = NULL;
  const char *finish = NULL;

  for (size_t i = 0; *p && i <= (size_t)end; i++) {
    if ((ssize_t)i == start)
      begin = p;
    if ((ssize_t)i == end) {
      finish = p;
      break;
    }
    p = g_utf8_next_char(p);
  }

  if (!begin)
    begin = self->str;
  if (!finish)
    finish = self->str + self->len;

  return g_string_new_len(begin, finish - begin);
}
