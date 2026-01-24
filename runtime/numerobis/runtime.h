#ifndef NUMEROBIS_RUNTIME_H
#define NUMEROBIS_RUNTIME_H

#include <gc.h>

/* Redirect GLib allocation to Boehm GC */
#define g_malloc(size) GC_MALLOC(size)
#define g_realloc(ptr, size) GC_REALLOC(ptr, size)
#define g_free(ptr) ((void)0)

#include <glib.h>

extern char *NUMEROBIS__FILE__;

void numerobis_runtime_init(void);

#endif
