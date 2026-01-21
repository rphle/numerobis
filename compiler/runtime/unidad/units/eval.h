#ifndef UNIDAD_EVAL_H
#define UNIDAD_EVAL_H

#include "units.h"
#include "../values.h"

extern gdouble unit_id_eval(uint16_t id, gdouble x);
extern gdouble base_unit(uint16_t id, gdouble x);
extern gdouble is_logarithmic(uint16_t id);

gdouble eval_unit(UnitNode *node, gdouble number, bool is_base);
GString *print_number(Number *n);

#endif
