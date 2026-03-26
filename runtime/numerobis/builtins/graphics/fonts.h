#ifndef NUMEROBIS_FONTS_H
#define NUMEROBIS_FONTS_H

#include <SDL2/SDL.h>
#include <SDL2/SDL_ttf.h>
#include <gc.h>
#include <glib.h>

extern const gchar *_font_path;

const gchar *_default_font(void);
const gchar *_resolve_font_name(const gchar *name);
TTF_Font *_get_font(const gchar *path, gint32 size, gint32 style);

void _cleanup_fonts(void);

#endif
