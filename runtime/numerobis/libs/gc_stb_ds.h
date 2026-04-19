#ifndef GC_STB_DS_H
#define GC_STB_DS_H

#include "../libs/bdwgc/include/gc.h"

#ifndef STBDS_REALLOC
#define STBDS_REALLOC(ctx, ptr, size) GC_realloc(ptr, size)
#define STBDS_FREE(ctx, ptr) GC_free(ptr)
#endif

#include "stb_ds.h"

#endif
