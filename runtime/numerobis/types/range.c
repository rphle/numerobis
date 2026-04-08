#include "range.h"
#include "../values.h"
#include "bool.h"
#include "methods.h"
#include "str.h"
#include <glib.h>
#include <stdbool.h>

static const ValueMethods _range_methods;

Value range__init__(Range x) {
  Value v;
  v.type = VALUE_RANGE;
  v.range = g_new(Range, 1);
  *v.range = x;
  return v;
}

static inline Value range__bool__(Value self) { return VTRUE; }
static inline bool range__cbool__(Value self) { return true; }

static Value range__eq__(Value _self, Value _other) {
  Range self = *_self.range;
  Range other = *_other.range;
  return bool__init__(self.start == other.start && self.stop == other.stop &&
                      self.step == other.step);
}

static inline Value range__str__(Value self) {
  return str__init__(sdsnew("[Range]"));
}

static const ValueMethods _range_methods = {
    .__bool__ = range__bool__,
    .__cbool__ = range__cbool__,
    .__eq__ = range__eq__,
    .__str__ = range__str__,
};

void range_methods_init(void) {
  NUMEROBIS_METHODS[VALUE_RANGE] = &_range_methods;
}
