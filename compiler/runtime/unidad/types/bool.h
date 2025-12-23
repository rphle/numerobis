#ifndef UNIDAD_BOOL_H
#define UNIDAD_BOOL_H

#include <glib.h>
#include <stdbool.h>

bool bool__bool__(bool self);
bool int__bool__(int self);
bool str__bool__(GString *self);

bool bool__eq__(bool self, bool other);

#endif
