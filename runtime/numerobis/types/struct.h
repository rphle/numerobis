#ifndef NUMEROBIS_STRUCT_H
#define NUMEROBIS_STRUCT_H

#include "../libs/sds.h"
#include "../values.h"
#include "str.h"

#include <stddef.h>
#include <stdint.h>

typedef struct {
  const char *name;
  const char **field_names;
  size_t fieldc;
} StructInfo;

extern const StructInfo STRUCT_REGISTRY[];

Value struct__init__(long id, long fieldc);
void struct_methods_init(void);

static inline sds struct__cstr__(Value self) {
  Value *fields = self.strukt;
  long id = fields[0].number.i64;

  const StructInfo *meta = &STRUCT_REGISTRY[id];

  sds s = sdsnew(meta->name);
  s = sdscat(s, "(");

  for (size_t i = 0; i < meta->fieldc; i++) {
    s = sdscatprintf(s, "%s=", meta->field_names[i]);
    sds fstr = __str__(fields[i + 1], NULL).str;
    s = sdscat(s, fstr);
    if (i + 1 < meta->fieldc)
      s = sdscat(s, ", ");
  }

  s = sdscat(s, ")");
  return s;
}

static inline Value struct__str__(Value self) {
  return str__init__(struct__cstr__(self));
}

#endif
