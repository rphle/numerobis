#ifndef NUMEROBIS_BOOL_H
#define NUMEROBIS_BOOL_H

#include "../values.h"
#include <stdbool.h>

#define VTRUE bool__init__(true)
#define VFALSE bool__init__(false)

Value bool__init__(bool x);

void bool_methods_init(void);

#endif
