#ifndef CONVERSIONS_H
#define CONVERSIONS_H

#include "../values.h"

Value *__to_str__(Value *val, const Location *loc);
Value *__to_int__(Value *val, const Location *loc);

#endif
