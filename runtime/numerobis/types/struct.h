#ifndef NUMEROBIS_STRUCT_H
#define NUMEROBIS_STRUCT_H

#include "../values.h"
#include "str.h"

#include <glib.h>
#include <stdint.h>

typedef struct {
  const char *name;
  const char **field_names;
  size_t fieldc;
} StructInfo;

extern const StructInfo STRUCT_REGISTRY[];

Value struct__init__(gint64 id, gint64 fieldc);
void struct_methods_init(void);

static GString *struct__cstr__(Value self) {
  Value *fields = self.strukt;
  gint64 id = fields[0].number.i64;

  const StructInfo *meta = &STRUCT_REGISTRY[id];

  GString *s = g_string_new(meta->name);
  g_string_append(s, "(");

  for (size_t i = 0; i < meta->fieldc; i++) {
    g_string_append_printf(s, "%s=", meta->field_names[i]);
    GString *fstr = __str__(fields[i + 1], NULL).str;
    g_string_append(s, fstr->str);
    if (i + 1 < meta->fieldc)
      g_string_append(s, ", ");
  }

  g_string_append(s, ")");
  return s;
}

static inline Value struct__str__(Value self) {
  return str__init__(struct__cstr__(self));
}

#endif
