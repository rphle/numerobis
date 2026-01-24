#ifndef NUMEROBIS_SOURCE_H
#define NUMEROBIS_SOURCE_H

#include <glib.h>

typedef struct {
    const gchar *path;
    const int n_lines;
    const gchar **source;
} NumerobisProgram;

extern GHashTable *NUMEROBIS_MODULE_REGISTRY;

#endif
