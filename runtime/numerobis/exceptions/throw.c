#include "throw.h"
#include "ansicolors.h"
#include "messages.h"
#include "source.h"
#include <gc.h>
#include <glib.h>
#include <locale.h>
#include <stdlib.h>

GHashTable *NUMEROBIS_MODULE_REGISTRY = NULL;
extern int NUMEROBIS__FILE__;
extern char *NUMEROBIS__FILES__[];

static size_t _strlen(const gchar *s) { return g_utf8_strlen(s, -1); }

static Location *_location_split(const Location *self, size_t *out_len) {
  int start = self->line;
  int end = (self->end_line != -1) ? self->end_line : self->line;

  if (end < start) {
    *out_len = 0;
    return NULL;
  }

  size_t count = (size_t)(end - start + 1);
  Location *lines = g_malloc(sizeof(Location) * count);
  if (!lines) {
    *out_len = 0;
    return NULL;
  }

  for (size_t i = 0; i < count; i++) {
    int line = start + (int)i;

    lines[i] = (Location){
        .line = line,
        .col = (line == self->line) ? self->col : 1,
        .end_line = line,
        .end_col = (line == self->end_line) ? self->end_col : -1,
    };
  }

  *out_len = count;
  return lines;
}

static void print_preview(const Location *span) {
  NumerobisProgram *program = g_hash_table_lookup(
      NUMEROBIS_MODULE_REGISTRY, NUMEROBIS__FILES__[NUMEROBIS__FILE__]);
  size_t n = 0;
  Location *lines = _location_split(span, &n);
  g_printerr("\n");
  for (size_t i = 0; i < n; i++) {
    const Location *line = &lines[i];
    const gchar *src = program->source[line->line - 1];
    size_t src_len = _strlen(src);

    int end_line = (line->end_line > 0) ? (line->end_line) : program->n_lines;
    int end_col = (line->end_col > 0) ? (line->end_col) : (int)src_len + 1;

    // clamp to valid range
    int col_start = MAX(1, MIN(line->col, (int)src_len + 1));
    int col_end = MAX(col_start, MIN(end_col, (int)src_len + 1)) + 1;

    gchar *src_ptr = (gchar *)src;
    gchar *col_start_ptr = g_utf8_offset_to_pointer(src_ptr, col_start - 1);
    gchar *col_end_ptr = g_utf8_offset_to_pointer(src_ptr, col_end - 1);

    int window_start_offset = MAX(0, col_start - 1 - 30);
    int window_end_offset = MIN((int)src_len, col_end - 1 + 30);

    gchar *window_start_ptr =
        g_utf8_offset_to_pointer(src_ptr, window_start_offset);
    gchar *window_end_ptr =
        g_utf8_offset_to_pointer(src_ptr, window_end_offset);

    gchar *before =
        g_strndup(window_start_ptr, col_start_ptr - window_start_ptr);
    gchar *highlight = g_strndup(col_start_ptr, col_end_ptr - col_start_ptr);
    gchar *after = g_strndup(col_end_ptr, window_end_ptr - col_end_ptr);

    // line number and prefix
    const char *prefix = (window_start_offset > 0) ? "..." : "";
    const char *suffix = (window_end_offset < (int)src_len) ? "..." : "";

    g_printerr(ANSI_DIM "%5d │" ANSI_RESET "   %s%s" ANSI_RED_BOLD
                        "%s" ANSI_RESET "%s%s\n",
               line->line, prefix, before, highlight, after, suffix);

    // underline
    size_t before_len = _strlen(before);
    size_t highlight_len = _strlen(highlight);
    size_t prefix_len = _strlen(prefix);

    if (highlight_len > 0) {
      GString *underline_str = g_string_new("");
      for (size_t j = 0; j < highlight_len; j++) {
        if (i == 0 && j == 0) {
          g_string_append(underline_str, "╰");
        } else if (i == n - 1 && j == highlight_len - 1) {
          g_string_append(underline_str, "╯");
        } else {
          g_string_append(underline_str, "─");
        }
      }

      g_printerr(ANSI_DIM "      │   " ANSI_RESET "%*s" ANSI_RED_BOLD
                          "%s" ANSI_RESET "\n",
                 (int)(prefix_len + before_len), "", underline_str->str);
    }
  }
}

void u_throw(const int code, const Location *span) {
  const RuntimeMessage *msg = NULL;
  for (size_t i = 0; i < G_N_ELEMENTS(NUMEROBIS_MESSAGES); i++) {
    if (NUMEROBIS_MESSAGES[i].code == code) {
      msg = &NUMEROBIS_MESSAGES[i];
      break;
    }
  }

  setlocale(LC_ALL, ""); // set locale for utf-8 output

  g_printerr(
      ANSI_RESET "" ANSI_RED_BOLD "%s" ANSI_RESET " " ANSI_DIM "at %s:%d:%d\n",
      msg->type, NUMEROBIS__FILES__[NUMEROBIS__FILE__], span->line, span->col);
  g_printerr("  [E%d] " ANSI_RESET "%s\n", code, msg->message);

  print_preview(span);

  exit(EXIT_FAILURE);
}
