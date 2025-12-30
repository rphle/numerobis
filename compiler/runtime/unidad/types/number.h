#ifndef UNIDAD_NUMBER_H
#define UNIDAD_NUMBER_H

#include "../values.h"
#include <glib.h>
#include <stdbool.h>

Value *int__init__(gint64 x);
Value *float__init__(gdouble x);

#endif
