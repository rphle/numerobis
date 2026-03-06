#ifndef NUMEROBIS_EVAL_H
#define NUMEROBIS_EVAL_H

#include "../values.h"
#include "units.h"

typedef enum { EVAL_INVERTED, EVAL_BASE, EVAL_NORMAL } EvalMode;

extern gdouble unit_id_eval(uint16_t id, gdouble x);
extern gdouble unit_id_eval_normal(uint16_t id, gdouble x);
extern gdouble base_unit(uint16_t id, gdouble x);
extern gdouble is_logarithmic(uint16_t id);

bool unit_is_logarithmic(const Unit *u);
gdouble eval_unit(const Unit *u, gdouble number, EvalMode mode);
GString *print_number(Number *n);
gdouble eval_number(Number *n, const uint64_t *_unit_hash);

#endif
