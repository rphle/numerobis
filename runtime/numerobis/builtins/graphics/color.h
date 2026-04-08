#ifndef NUMEROBIS_COLOR_H
#define NUMEROBIS_COLOR_H

#include <glib.h>
#include <stdint.h>

typedef struct {
  uint8_t r, g, b, a;
} Color;
static const Color COLOR_BLACK = {0, 0, 0, 255};

Color _parse_color(const char *s);

#endif
