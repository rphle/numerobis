#ifndef NUMEROBIS_UTILS_H
#define NUMEROBIS_UTILS_H

#include "../values.h"
#include <glib.h>
#include <sys/types.h>

ssize_t normalize_index(ssize_t index, ssize_t len);
void normalize_slice(ssize_t len, ssize_t *start, ssize_t *stop, ssize_t *step);

inline gint64 _i64(Value value) { return value.number.i64; }
inline gdouble _f64(Value value) {
  Number n = value.number;
  if (n.kind == NUM_INT64)
    return (gdouble)n.i64;
  return n.f64;
}
inline const gchar *_str(Value value) { return value.str->str; }
inline gboolean _bool(Value value) {
  return (value.type == VALUE_BOOL) ? (gboolean)value.boolean
                                    : (gboolean)value.number.i64;
}

#endif
