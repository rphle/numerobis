#include <SDL2/SDL.h>
#include <SDL2/SDL_ttf.h>
#include <gc.h>
#include <glib.h>
#include <stdio.h>
#include <string.h>

const gchar *_font_path = NULL;

static GHashTable *_fc_cache = NULL;

static const gchar *_fallback_fonts[] = {
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    NULL,
};

const gchar *_default_font(void) {
  if (_font_path)
    return _font_path;
  for (int i = 0; _fallback_fonts[i]; i++) {
    if (g_file_test(_fallback_fonts[i], G_FILE_TEST_EXISTS))
      return _fallback_fonts[i];
  }
  return NULL;
}

const gchar *_resolve_font_name(const gchar *name) {
  if (!name || *name == '\0')
    return NULL;
  if (!_fc_cache)
    _fc_cache = g_hash_table_new(g_str_hash, g_str_equal);

  gchar *cached = g_hash_table_lookup(_fc_cache, name);
  if (cached)
    return cached;

  gchar *cmd = g_strdup_printf("fc-match --format='%%{file}' '%s'", name);
  gchar *output = NULL;
  GError *err = NULL;
  gboolean ok = g_spawn_command_line_sync(cmd, &output, NULL, NULL, &err);
  g_free(cmd);

  if (!ok || !output || *output == '\0') {
    if (err)
      g_error_free(err);
    g_free(output);
    fprintf(stderr, "graphics: fc-match failed for font \"%s\"\n", name);
    return NULL;
  }

  g_strstrip(output);
  if (*output == '\'')
    output++;
  gsize olen = strlen(output);
  if (olen > 0 && output[olen - 1] == '\'')
    output[olen - 1] = '\0';

  gchar *path = GC_STRDUP(output);
  g_free(output);
  g_hash_table_insert(_fc_cache, GC_STRDUP(name), path);
  return path;
}

typedef struct {
  const gchar *path;
  gint32 size;
  gint32 style;
} FontKey;
static GHashTable *_font_cache = NULL;

static guint _fk_hash(gconstpointer k) {
  const FontKey *f = k;
  return g_str_hash(f->path) ^ (guint)(f->size * 31) ^ (guint)(f->style << 16);
}
static gboolean _fk_equal(gconstpointer a, gconstpointer b) {
  const FontKey *fa = a, *fb = b;
  return fa->size == fb->size && fa->style == fb->style &&
         strcmp(fa->path, fb->path) == 0;
}

TTF_Font *_get_font(const gchar *path, gint32 size, gint32 style) {
  if (!path)
    return NULL;
  if (!_font_cache)
    _font_cache = g_hash_table_new(_fk_hash, _fk_equal);

  FontKey lookup = {path, size, style};
  TTF_Font *font = g_hash_table_lookup(_font_cache, &lookup);
  if (font)
    return font;

  font = TTF_OpenFont(path, size);
  if (!font) {
    fprintf(stderr, "graphics: TTF_OpenFont(\"%s\", %d): %s\n", path, size,
            TTF_GetError());
    return NULL;
  }
  TTF_SetFontStyle(font, style);

  FontKey *key = GC_MALLOC(sizeof(FontKey));
  key->path = GC_STRDUP(path);
  key->size = size;
  key->style = style;
  g_hash_table_insert(_font_cache, key, font);
  return font;
}

void _cleanup_fonts(void) {
  if (_font_cache) {
    GHashTableIter iter;
    gpointer key, value;
    g_hash_table_iter_init(&iter, _font_cache);
    while (g_hash_table_iter_next(&iter, &key, &value)) {
      TTF_CloseFont((TTF_Font *)value);
    }
    g_hash_table_destroy(_font_cache);
    _font_cache = NULL;
  }
  if (_fc_cache) {
    g_hash_table_destroy(_fc_cache);
    _fc_cache = NULL;
  }
}
