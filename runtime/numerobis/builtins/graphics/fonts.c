#include <SDL2/SDL.h>
#include <SDL2/SDL_ttf.h>
#include <dirent.h>
#include <gc.h>
#include <glib.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

const gchar *_font_path = NULL;

static GHashTable *_fc_cache = NULL;

static const char *linux_font_dirs[] = {"/usr/share/fonts",
                                        "/usr/local/share/fonts",
                                        "/usr/share/fonts/truetype",
                                        "/usr/share/fonts/opentype",
                                        "/usr/share/fonts/TTF",
                                        "/usr/share/fonts/Type1",
                                        "/usr/share/fonts/misc",
                                        "/usr/share/X11/fonts",
                                        "~/.local/share/fonts",
                                        "~/.fonts",
                                        NULL};

static const gchar *PREFERRED_FONTS[] = {"Roboto-Regular.ttf",
                                         "Ubuntu-R.ttf",
                                         "DejaVuSans.ttf",
                                         "FreeSans.ttf",
                                         "LiberationSans-Regular.ttf",
                                         NULL};

static gboolean is_preferred(const gchar *name) {
  for (int i = 0; PREFERRED_FONTS[i]; i++)
    if (g_ascii_strcasecmp(name, PREFERRED_FONTS[i]) == 0)
      return TRUE;
  return FALSE;
}

static void scan_dir(const gchar *path) {
  GDir *dir = g_dir_open(path, 0, NULL);
  if (!dir || _font_path)
    return;

  const gchar *name;
  while ((name = g_dir_read_name(dir)) && !_font_path) {
    gchar *full = g_build_filename(path, name, NULL);

    if (g_file_test(full, G_FILE_TEST_IS_DIR)) {
      scan_dir(full);
    } else if (g_str_has_suffix(name, ".ttf") && is_preferred(name)) {
      _font_path = g_steal_pointer(&full);
    }

    g_free(full);
  }
  g_dir_close(dir);
}

const gchar *_default_font(void) {
  if (_font_path)
    return _font_path;

  GPtrArray *paths = g_ptr_array_new_with_free_func(g_free);
  g_ptr_array_add(paths,
                  g_build_filename(g_get_user_data_dir(), "fonts", NULL));
  g_ptr_array_add(paths, g_build_filename(g_get_home_dir(), ".fonts", NULL));

  for (int i = 0; linux_font_dirs[i]; i++)
    g_ptr_array_add(paths, g_strdup(linux_font_dirs[i]));

  for (guint i = 0; i < paths->len && !_font_path; i++) {
    scan_dir(g_ptr_array_index(paths, i));
  }

  g_ptr_array_unref(paths);
  return _font_path;
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
  if (fa->size != fb->size || fa->style != fb->style)
    return FALSE;
  if (fa->path == fb->path)
    return TRUE;
  if (!fa->path || !fb->path)
    return FALSE;
  return strcmp(fa->path, fb->path) == 0;
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
