#ifndef NUMEROBIS_FONTS_H
#define NUMEROBIS_FONTS_H

#include <SDL2/SDL.h>
#include <SDL2/SDL_ttf.h>
#include <gc.h>
#include <glib.h>

extern const char *_font_path;

const char *_default_font(void);
const char *_resolve_font_name(const char *name);
TTF_Font *_get_font(const char *path, int size, int style);

void _cleanup_fonts(void);

#endif
