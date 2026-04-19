#include "fonts.h"
#include "../../libs/gc_stb_ds.h"
#include "../../libs/sds.h"

#include <SDL2/SDL.h>
#include <SDL2/SDL_ttf.h>
#include <dirent.h>
#include "../../libs/bdwgc/include/gc.h"
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

const char *_font_path = NULL;
static FcEntry *_fc_cache = NULL;

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
        _font_path = GC_STRDUP(full);
      }
    }
    sdsfree(full);
  }
  closedir(d);
}

const char *_default_font(void) {
  if (_font_path)
    return _font_path;

  char *home = getenv("HOME");

  /* Search home dirs first, then system dirs */
  if (home) {
    sds p1 = sdscatprintf(sdsempty(), "%s/.local/share/fonts", home);
    sds p2 = sdscatprintf(sdsempty(), "%s/.fonts", home);
    scan_dir(p1);
    scan_dir(p2);
    sdsfree(p1);
    sdsfree(p2);
  }

  for (int i = 0; linux_font_dirs[i] && !_font_path; i++)
    scan_dir(linux_font_dirs[i]);

  return _font_path;
}

const char *_resolve_font_name(const char *name) {
  if (!name || *name == '\0')
    return NULL;

  FcEntry *entry = shgetp_null(_fc_cache, name);
  if (entry)
    return entry->value;

  sds cmd = sdscatprintf(sdsempty(), "fc-match --format='%%{file}' '%s'", name);
  FILE *fp = popen(cmd, "r");
  sdsfree(cmd);

  if (!fp)
    return NULL;

  char output[1024];
  if (fgets(output, sizeof(output), fp) != NULL) {
    pclose(fp);
    /* Strip surrounding quotes and whitespace */
    char *start = output;
    while (*start == '\'' || *start == ' ' || *start == '\n')
      start++;
    char *end = start + strlen(start) - 1;
    while (end > start && (*end == '\'' || *end == ' ' || *end == '\n')) {
      *end = '\0';
      end--;
    }

    char *path = GC_STRDUP(start);
    shput(_fc_cache, name, path);
    return path;
  }
  pclose(fp);
  return NULL;
}

static FontEntry *_font_cache = NULL;

TTF_Font *_get_font(const char *path, int size, int style) {
  if (!path)
    return NULL;

  for (ptrdiff_t i = 0; i < arrlen(_font_cache); i++) {
    FontEntry *e = &_font_cache[i];
    if (e->key.size == size && e->key.style == style &&
        strcmp(e->key.path, path) == 0)
      return e->value;
  }

  TTF_Font *font = TTF_OpenFont(path, size);
  if (!font)
    return NULL;
  TTF_SetFontStyle(font, style);

  FontEntry e = {.key = {.path = strdup(path), .size = size, .style = style},
                 .value = font};
  arrput(_font_cache, e);
  return font;
}

void _cleanup_fonts(void) {
  for (ptrdiff_t i = 0; i < arrlen(_font_cache); i++) {
    TTF_CloseFont(_font_cache[i].value);
    free(_font_cache[i].key.path);
  }
  arrfree(_font_cache);
  _font_cache = NULL;

  shfree(_fc_cache);
  _fc_cache = NULL;
}
