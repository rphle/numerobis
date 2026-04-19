#ifndef NUMEROBIS_FONTS_H
#define NUMEROBIS_FONTS_H

#include <SDL2/SDL.h>
#include <SDL2/SDL_ttf.h>
#include "../../libs/bdwgc/include/gc.h"

extern const char *_font_path;

typedef struct {
  char *key;
  char *value;
} FcEntry;

typedef struct {
  char *path;
  int size;
  int style;
} FontKey;

typedef struct {
  FontKey key;
  TTF_Font *value;
} FontEntry;

const char *_default_font(void);
const char *_resolve_font_name(const char *name);
TTF_Font *_get_font(const char *path, int size, int style);

void _cleanup_fonts(void);

#endif
