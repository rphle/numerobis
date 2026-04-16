#ifndef NUMEROBIS_UTILS_H
#define NUMEROBIS_UTILS_H

#include "../values.h"
#include <stdbool.h>
#include <sys/types.h>

ssize_t normalize_index(ssize_t index, ssize_t len);
void normalize_slice(ssize_t len, ssize_t *start, ssize_t *stop, ssize_t *step);
size_t count_utf8_code_points(const char *s);

inline long _i64(Value value) { return value.number.i64; }
inline double _f64(Value value) {
  Number n = value.number;
  if (n.kind == NUM_INT64)
    return (double)n.i64;
  return n.f64;
}
inline const sds _str(Value value) { return value.str; }
inline bool _bool(Value value) {
  return (value.type == VALUE_BOOL) ? (bool)value.boolean
                                    : (bool)value.number.i64;
}

static const char *utf8_next_char(const char *p, const char *end) {
  const unsigned char *u = (const unsigned char *)p;
  if (p >= end)
    return p;
  // Skip continuation bytes (10xxxxxx) to find the next codepoint start.
  do {
    ++u;
  } while (u < (const unsigned char *)end && (*u & 0xC0) == 0x80);
  return (const char *)u;
}

// g_utf8_offset_to_pointer
static char *utf8_offset_to_pointer(const char *str, int offset) {
  const char *p = str;
  while (offset > 0 && *p) {
    if ((*p & 0xc0) != 0x80)
      offset--;
    p++;
  }
  return (char *)p;
}

bool is_absolute(const char *path);
sds get_absolute_resource_path(const char *input_path);

#endif
