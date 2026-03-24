#ifndef NUMEROBIS_COLOR_H
#define NUMEROBIS_COLOR_H

#include <glib.h>

typedef struct {
  guint8 r, g, b, a;
} Color;
static const Color COLOR_BLACK = {0, 0, 0, 255};

Color _parse_color(const gchar *s);

#endif
