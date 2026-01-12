#ifndef UNIDAD_UNITS_H
#define UNIDAD_UNITS_H

#include <glib.h>
#include <math.h>

#define UNIT(name, def)                                                        \
  gdouble __unit##name(gdouble _) { return def; };
#define LOGN(b, x) (log(x) / log(b))

#endif
