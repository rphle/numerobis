#ifndef NUMEROBIS_RANGE_H
#define NUMEROBIS_RANGE_H

#include "glib.h"
struct Value;
typedef struct Value Value;

typedef struct Range {
  gint64 start;
  gint64 stop;
  gdouble step;
} Range;

Value range__init__(Range x);
void range_methods_init(void);

#endif
