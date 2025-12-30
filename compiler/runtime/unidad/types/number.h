#ifndef UNIDAD_NUMBER_H
#define UNIDAD_NUMBER_H

#include <glib.h>
#include <stdbool.h>

bool int__bool__(gint64 self);

bool int__lt__(gint64 self, gint64 other);
bool int__le__(gint64 self, gint64 other);
bool int__gt__(gint64 self, gint64 other);
bool int__ge__(gint64 self, gint64 other);

bool int__eq__(gint64 self, gint64 other);

bool float__bool__(gdouble self);

bool float__lt__(gdouble self, gdouble other);
bool float__le__(gdouble self, gdouble other);
bool float__gt__(gdouble self, gdouble other);
bool float__ge__(gdouble self, gdouble other);

bool float__eq__(gdouble self, gdouble other);

#endif
