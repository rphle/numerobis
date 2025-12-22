#include <glib.h>
#include <stddef.h>

GString *str__getitem__(GString *self, size_t index) {
  const char *p = self->str;

  for (size_t i = 0; i < index; i++) {
    if (*p == '\0')
      return g_string_new(""); // out of bounds
    p = g_utf8_next_char(p);
  }

  if (*p == '\0')
    return g_string_new("");

  gunichar ch = g_utf8_get_char(p);

  gchar buf[8];
  gint len = g_unichar_to_utf8(ch, buf);
  buf[len] = '\0';

  return g_string_new(buf);
}
