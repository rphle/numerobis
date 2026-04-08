#ifndef NUMEROBIS_RUNTIME_H
#define NUMEROBIS_RUNTIME_H

#include <gc.h>

/* Redirect GLib allocation to Boehm GC */
#define g_malloc(size) GC_MALLOC(size)
#define g_realloc(ptr, size) GC_REALLOC(ptr, size)
#define g_free(ptr) GC_FREE(ptr)

#include <glib.h>

extern int NUMEROBIS__FILE__;
extern const char *NUMEROBIS__FILES__[];
extern char **NUMEROBIS__ARGV__;

void numerobis_runtime_init(void);
void restart_program(void);

#endif
