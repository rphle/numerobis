#ifndef UNIDAD_BOOL_H
#define UNIDAD_BOOL_H

#include "../values.h"
#include <glib.h>
#include <stdbool.h>

#define VTRUE bool__init__(true)
#define VFALSE bool__init__(false)

Value *bool__init__(bool x);

#endif
