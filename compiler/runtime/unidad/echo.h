#ifndef ECHO_H
#define ECHO_H

#include <glib.h>
#include <stdbool.h>
#include <stdio.h>

static inline void echo_double(double x) { printf("%g\n", x); }
static inline void echo_float(float x) { printf("%g\n", x); }
static inline void echo_long(long x) { printf("%ld\n", x); }
static inline void echo_int(int x) { printf("%d\n", x); }
static inline void echo_cstr(const char *x) { puts(x); }
static inline void echo_string(GString *x) { puts(x->str); }
static inline void echo_bool(bool x) { printf("%s\n", x ? "true" : "false"); }
static inline void echo_ptr(const void *x) { printf("[unsupported: %p]\n", x); }

#define echo(x)                                                                \
  _Generic((x),                                                                \
      double: echo_double,                                                     \
      float: echo_float,                                                       \
      long: echo_long,                                                         \
      int: echo_int,                                                           \
      char *: echo_cstr,                                                       \
      const char *: echo_cstr,                                                 \
      GString *: echo_string,                                                  \
      bool: echo_bool,                                                         \
      default: echo_ptr)(x)

#endif
