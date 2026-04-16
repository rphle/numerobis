#include "../constants.h"
#include "../libs/whereami.h"

#include <gc.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
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

// Source - https://stackoverflow.com/a/32936928
// Posted by chqrlie, modified by community. See post 'Timeline' for change
// history Retrieved 2026-04-08, License - CC BY-SA 4.0

size_t count_utf8_code_points(const char *s) {
  size_t count = 0;
  while (*s) {
    count += (*s++ & 0xC0) != 0x80;
  }
  return count;
}


bool is_absolute(const char *path) {
    if (!path) return 0;
#ifdef _WIN32
    // Windows: starts with "C:\" or "\\"
    return (strlen(path) > 2 && isalpha(path[0]) && path[1] == ':') || (path[0] == '\\' && path[1] == '\\');
#else
    // Unix/Linux/macOS: starts with "/"
    return path[0] == '/';
#endif
}

sds get_absolute_resource_path(const char *input_path) {
    if (is_absolute(input_path)) {
        return sdsnew(input_path);
    }

    // Get the directory of the binary
    int dirlen;
    int len = wai_getExecutablePath(NULL, 0, &dirlen);
    char* buffer = GC_MALLOC(len + 1);
    wai_getExecutablePath(buffer, len, &dirlen);

    sds final_path = sdsnewlen(buffer, dirlen);
    char last_char = final_path[sdslen(final_path) - 1];
    if (last_char != '/' && last_char != '\\') {
        final_path = sdscat(final_path, "/");
    }

    final_path = sdscat(final_path, input_path);
    return final_path;
}
