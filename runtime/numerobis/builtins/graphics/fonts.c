#include "../../libs/sds.h"

#include <SDL2/SDL.h>
#include <SDL2/SDL_ttf.h>
#include <dirent.h>
#include <gc.h>
#include <glib.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

const char *_font_path = NULL;

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

static const char *PREFERRED_FONTS[] = {"Roboto-Regular.ttf",
                                        "Ubuntu-R.ttf",
                                        "DejaVuSans.ttf",
                                        "FreeSans.ttf",
                                        "LiberationSans-Regular.ttf",
                                        NULL};

static bool is_preferred(const char *name) {
  for (int i = 0; PREFERRED_FONTS[i]; i++)
    if (strcasecmp(name, PREFERRED_FONTS[i]) == 0)
      return true;
  return false;
}

static void scan_dir(const char *path) {
  DIR *d = opendir(path);
  if (!d || _font_path)
    return;

  struct dirent *dir;
  while ((dir = readdir(d)) != NULL && !_font_path) {
    if (dir->d_name[0] == '.')
      continue;

    sds full = sdscatprintf(sdsempty(), "%s/%s", path, dir->d_name);
    struct stat st;
    if (stat(full, &st) == 0) {
      if (S_ISDIR(st.st_mode)) {
        scan_dir(full);
      } else if (strstr(dir->d_name, ".ttf") && is_preferred(dir->d_name)) {
        _font_path = strdup(full);
      }
    }
    sdsfree(full);
  }
  closedir(d);
}

const char *_default_font(void) {
  if (_font_path)
    return _font_path;

  GPtrArray *paths = g_ptr_array_new_with_free_func(free);
  char *home = getenv("HOME");
  if (home) {
    g_ptr_array_add(
        paths, strdup(sdscatprintf(sdsempty(), "%s/.local/share/fonts", home)));
    g_ptr_array_add(paths, strdup(sdscatprintf(sdsempty(), "%s/.fonts", home)));
  }

  for (int i = 0; linux_font_dirs[i]; i++)
    g_ptr_array_add(paths, strdup(linux_font_dirs[i]));

  for (unsigned int i = 0; i < paths->len && !_font_path; i++) {
    scan_dir(g_ptr_array_index(paths, i));
  }

  g_ptr_array_unref(paths);
  return _font_path;
}

const char *_resolve_font_name(const char *name) {
  if (!name || *name == '\0')
    return NULL;
  if (!_fc_cache)
    _fc_cache = g_hash_table_new_full(g_str_hash, g_str_equal, free, free);

  char *cached = g_hash_table_lookup(_fc_cache, name);
  if (cached)
    return cached;

  sds cmd = sdscatprintf(sdsempty(), "fc-match --format='%%{file}' '%s'", name);
  FILE *fp = popen(cmd, "r");
  sdsfree(cmd);

  if (!fp)
    return NULL;

  char output[1024];
  if (fgets(output, sizeof(output), fp) != NULL) {
    pclose(fp);
    // Strip surrounding quotes and whitespace
    char *start = output;
    while (*start == '\'' || *start == ' ' || *start == '\n')
      start++;
    char *end = start + strlen(start) - 1;
    while (end > start && (*end == '\'' || *end == ' ' || *end == '\n')) {
      *end = '\0';
      end--;
    }

    char *path = strdup(start);
    g_hash_table_insert(_fc_cache, strdup(name), path);
    return path;
  }
  pclose(fp);
  return NULL;
}

typedef struct {
  char *path;
  int size;
  int style;
} FontKey;
static GHashTable *_font_cache = NULL;

static unsigned int _fk_hash(gconstpointer k) {
  const FontKey *f = k;
  unsigned int h = (unsigned int)g_str_hash(f->path);
  return h ^ (unsigned int)(f->size * 31) ^ (unsigned int)(f->style << 16);
}

static int _fk_equal(gconstpointer a, gconstpointer b) {
  const FontKey *fa = a, *fb = b;
  return (fa->size == fb->size && fa->style == fb->style &&
          strcmp(fa->path, fb->path) == 0);
}

TTF_Font *_get_font(const char *path, int size, int style) {
  if (!path)
    return NULL;
  if (!_font_cache)
    _font_cache = g_hash_table_new_full(_fk_hash, _fk_equal, free, NULL);

  FontKey lookup = {(char *)path, size, style};
  TTF_Font *font = g_hash_table_lookup(_font_cache, &lookup);
  if (font)
    return font;

  font = TTF_OpenFont(path, size);
  if (!font)
    return NULL;
  TTF_SetFontStyle(font, style);

  FontKey *key = malloc(sizeof(FontKey));
  key->path = strdup(path);
  key->size = size;
  key->style = style;
  g_hash_table_insert(_font_cache, key, font);
  return font;
}

void _cleanup_fonts(void) {
  if (_font_cache) {
    GHashTableIter iter;
    void *key, *value;
    g_hash_table_iter_init(&iter, _font_cache);
    while (g_hash_table_iter_next(&iter, &key, &value)) {
      TTF_CloseFont((TTF_Font *)value);
      free(((FontKey *)key)->path);
    }
    g_hash_table_destroy(_font_cache);
    _font_cache = NULL;
  }
  if (_fc_cache) {
    g_hash_table_destroy(_fc_cache);
    _fc_cache = NULL;
  }
}
