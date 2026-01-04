#ifndef UNIDAD_RUNTIME_H
#define UNIDAD_RUNTIME_H

#include <gc.h>

/* Redirect GLib allocation to Boehm GC */
#define g_malloc(size) GC_MALLOC(size)
#define g_realloc(ptr, size) GC_REALLOC(ptr, size)
#define g_free(ptr) ((void)0)

#include <glib.h>

extern char *UNIDAD__FILE__;

void unidad_runtime_init(void);

#endif
