#ifndef NUMEROBIS_UTILS_H
#define NUMEROBIS_UTILS_H

#include "../values.h"
#include <glib.h>
#include <sys/types.h>

ssize_t normalize_index(ssize_t index, ssize_t len);
void normalize_slice(ssize_t len, ssize_t *start, ssize_t *stop, ssize_t *step);

inline gint64 _i64(Value *args, int i) { return args[i].number.i64; }
inline gdouble _f64(Value *args, int i) { return args[i].number.f64; }
inline const gchar *_str(Value *args, int i) { return args[i].str->str; }
inline gboolean _bool(Value *args, int i) {
  Value v = args[i];
  return (v.type == VALUE_BOOL) ? (gboolean)v.boolean : (gboolean)v.number.i64;
}

#endif
