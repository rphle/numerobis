#include "color.h"

#include <glib.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

/* Color  (#RGB / #RRGGBB / #RRGGBBAA, leading '#' optional) */
Color _parse_color(const char *s) {
  if (!s || *s == '\0')
    return COLOR_BLACK;
  if (*s == '#')
    s++;

  gsize len = strlen(s);
  for (gsize i = 0; i < len; i++) {
    if (!g_ascii_isxdigit(s[i])) {
      fprintf(stderr, "graphics: invalid colour \"%s\"\n", s);

      return COLOR_BLACK;
    }
  }

  uint32_t v = 0;
  if (len == 3) {
    uint8_t rv = g_ascii_xdigit_value(s[0]);
    uint8_t gv = g_ascii_xdigit_value(s[1]);
    uint8_t bv = g_ascii_xdigit_value(s[2]);
    return (Color){rv | (rv << 4), gv | (gv << 4), bv | (bv << 4), 255};
  }
  if (len == 6) {
    sscanf(s, "%06x", &v);
    return (Color){(v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF, 255};
  }
  if (len == 8) {
    sscanf(s, "%08x", &v);
    return (Color){(v >> 24) & 0xFF, (v >> 16) & 0xFF, (v >> 8) & 0xFF,
                   v & 0xFF};
  }

  fprintf(stderr, "graphics: invalid colour length for \"%s\"\n", s);
  return COLOR_BLACK;
}
