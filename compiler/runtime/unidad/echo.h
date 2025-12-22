#ifndef ECHO_H
#define ECHO_H

#include <stdio.h>

static inline void echo_double(double x) { printf("%g\n", x); }

static inline void echo_float(float x) { printf("%g\n", x); }

static inline void echo_long(long x) { printf("%ld\n", x); }

static inline void echo_int(int x) { printf("%d\n", x); }

static inline void echo_cstr(const char *x) { puts(x); }

static inline void echo_ptr(const void *x) { printf("[unsupported: %p]\n", x); }

#define echo(x)                                                                \
  _Generic((x),                                                                \
      double: echo_double,                                                     \
      float: echo_float,                                                       \
      long: echo_long,                                                         \
      int: echo_int,                                                           \
      char *: echo_cstr,                                                       \
      const char *: echo_cstr,                                                 \
      default: echo_ptr)(x)

#endif
