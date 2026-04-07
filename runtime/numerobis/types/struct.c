#include "struct.h"
#include "../values.h"
#include "bool.h"
#include "methods.h"
#include "number.h"

#include <glib.h>
#include <stdbool.h>
#include <stddef.h>

static const ValueMethods _struct_methods;

Value struct__init__(gint64 id, gint64 fieldc) {
  const StructInfo *meta = &STRUCT_REGISTRY[id];
  Value v;
  v.type = VALUE_STRUCT;
  v.strukt = g_new(Value, fieldc + 1);
  v.strukt[0] = int__init__(id, U_ONE);
  return v;
}

static inline Value struct__bool__(Value self) { return VTRUE; }

static inline bool struct__cbool__(Value self) { return true; }

static inline Value struct__eq__(Value _self, Value _other) {
  Value *self = _self.strukt;
  Value *other = _other.strukt;

  gint64 id = self[0].number.i64;

  if (id != other[0].number.i64)
    return VFALSE;

  size_t fieldc = STRUCT_REGISTRY[id].fieldc;

  for (size_t i = 1; i <= fieldc; i++) {
    if (!__eq__(self[i], other[i]).boolean)
      return VFALSE;
  }

  return VTRUE;
}

static const ValueMethods _struct_methods = {
    .__bool__ = struct__bool__,
    .__cbool__ = struct__cbool__,
    .__eq__ = struct__eq__,
    .__str__ = struct__str__,
};

void struct_methods_init(void) {
  NUMEROBIS_METHODS[VALUE_STRUCT] = &_struct_methods;
}
