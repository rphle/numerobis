#ifndef NUMEROBIS_EVAL_H
#define NUMEROBIS_EVAL_H

#include "../values.h"
#include "units.h"

typedef enum { EVAL_INVERTED, EVAL_BASE, EVAL_NORMAL } EvalMode;

extern double unit_id_eval(uint16_t id, double x);
extern double unit_id_eval_normal(uint16_t id, double x);
extern double base_unit(uint16_t id, double x);
extern double is_logarithmic(uint16_t id);

bool unit_is_logarithmic(const Unit *u);
double eval_unit(const Unit *u, double number, EvalMode mode);
GString *print_number(Number *n);
double eval_number(Number *n, const uint64_t *_unit_hash);

#endif
