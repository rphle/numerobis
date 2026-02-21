#ifndef NUMEROBIS_SIMPLIFIER_H
#define NUMEROBIS_SIMPLIFIER_H

#include "units.h"

/**
 * Simplify a unit expression tree.
 * Translated rather verbosely from Python Simplifier class.
 */
UnitNode *unit_simplify(UnitNode *node);

#endif
