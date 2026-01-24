#ifndef NUMEROBIS_UTILS_H
#define NUMEROBIS_UTILS_H

#include <sys/types.h>

ssize_t normalize_index(ssize_t index, ssize_t len);
void normalize_slice(ssize_t len, ssize_t *start, ssize_t *stop, ssize_t *step);

#endif
