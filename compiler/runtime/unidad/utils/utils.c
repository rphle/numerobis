#include "../constants.h"
#include <stddef.h>
#include <sys/types.h>

ssize_t normalize_index(ssize_t index, ssize_t len) {
  if (index < 0)
    index += len;
  if (index < 0 || (size_t)index >= len)
    return -1;
  return index;
}

void normalize_slice(ssize_t len, ssize_t *start, ssize_t *stop,
                     ssize_t *step) {
  ssize_t s = *start, e = *stop, st = *step;

  if (st == SLICE_NONE)
    st = 1;
  if (s == SLICE_NONE)
    s = (st > 0) ? 0 : len - 1;
  if (e == SLICE_NONE)
    e = (st > 0) ? len : -len - 1;

  // negative indices
  if (s < 0)
    s += len;
  if (e < 0)
    e += len;

  /* Clamp to valid range */
  if (st > 0) {
    s = (s < 0) ? 0 : (s > len) ? len : s;
    e = (e < 0) ? 0 : (e > len) ? len : e;
  } else {
    s = (s < -1) ? -1 : (s >= len) ? len - 1 : s;
    e = (e < -1) ? -1 : (e >= len) ? len - 1 : e;
  }

  *start = s;
  *stop = e;
  *step = st;
}
