#include "throw.h"
#include "../libs/sds.h"
#include "../types/str.h"
#include "../utils/utils.h"
#include "ansicolors.h"
#include "messages.h"
#include "source.h"

#include <gc.h>
#include <glib.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

GHashTable *NUMEROBIS_MODULE_REGISTRY = NULL;
extern int NUMEROBIS__FILE__;
extern char *NUMEROBIS__FILES__[];

static Location *_location_split(const Location *self, size_t *out_len) {
  int start = self->line;
  int end = (self->end_line != -1) ? self->end_line : self->line;

  if (end < start) {
    *out_len = 0;
    return NULL;
  }

  size_t count = (size_t)(end - start + 1);
  Location *lines = GC_MALLOC(sizeof(Location) * count);
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
  fprintf(stderr, "\n");

  for (size_t i = 0; i < n; i++) {
    const Location *line = &lines[i];
    const char *src = program->source[line->line - 1];
    size_t src_len = _str_len(src);

    int end_col = (line->end_col > 0) ? (line->end_col) : (int)src_len + 1;
    int col_start =
        (line->col < 1)
            ? 1
            : (line->col > (int)src_len + 1 ? (int)src_len + 1 : line->col);
    int col_end =
        (end_col < col_start)
            ? col_start
            : (end_col > (int)src_len + 1 ? (int)src_len + 1 : end_col);

    char *src_ptr = (char *)src;
    char *col_start_ptr = utf8_offset_to_pointer(src_ptr, col_start - 1);
    char *col_end_ptr = utf8_offset_to_pointer(src_ptr, col_end);

    int window_start_offset = (col_start - 1 - 30 < 0) ? 0 : col_start - 1 - 30;
    int window_end_offset =
        (col_end + 30 > (int)src_len) ? (int)src_len : col_end + 30;

    char *window_start_ptr =
        utf8_offset_to_pointer(src_ptr, window_start_offset);
    char *window_end_ptr = utf8_offset_to_pointer(src_ptr, window_end_offset);

    sds before = sdsnewlen(window_start_ptr, col_start_ptr - window_start_ptr);
    sds highlight = sdsnewlen(col_start_ptr, col_end_ptr - col_start_ptr);
    sds after = sdsnewlen(col_end_ptr, window_end_ptr - col_end_ptr);

    const char *prefix = (window_start_offset > 0) ? "..." : "";
    const char *suffix = (window_end_offset < (int)src_len) ? "..." : "";

    fprintf(stderr,
            ANSI_DIM "%5d │" ANSI_RESET "   %s%s" ANSI_RED_BOLD "%s" ANSI_RESET
                     "%s%s\n",
            line->line, prefix, before, highlight, after, suffix);

    size_t highlight_len = _str_len(highlight);
    if (highlight_len > 0) {
      sds underline_str = sdsempty();
      for (size_t j = 0; j < highlight_len; j++) {
        if (i == 0 && j == 0)
          underline_str = sdscat(underline_str, "╰");
        else if (i == n - 1 && j == highlight_len - 1)
          underline_str = sdscat(underline_str, "╯");
        else
          underline_str = sdscat(underline_str, "─");
      }

      fprintf(stderr,
              ANSI_DIM "      │   " ANSI_RESET "%*s" ANSI_RED_BOLD
                       "%s" ANSI_RESET "\n",
              (int)(_str_len(prefix) + _str_len(before)), "", underline_str);
      sdsfree(underline_str);
    }

    sdsfree(before);
    sdsfree(highlight);
    sdsfree(after);
  }
}

void u_throw(const int code, const RuntimeMessage *msg, const Location *span) {
  if (msg == NULL) {
    for (size_t i = 0;
         i < sizeof(NUMEROBIS_MESSAGES) / sizeof(NUMEROBIS_MESSAGES[0]); i++) {
      if (NUMEROBIS_MESSAGES[i].code == code) {
        msg = &NUMEROBIS_MESSAGES[i];
        break;
      }
    }
  }

  fprintf(
      stderr,
      ANSI_RESET "" ANSI_RED_BOLD "%s" ANSI_RESET " " ANSI_DIM "at %s:%d:%d\n",
      msg->type, NUMEROBIS__FILES__[NUMEROBIS__FILE__], span->line, span->col);
  fprintf(stderr, "  [E%d] " ANSI_RESET "%s\n", code, msg->message);

  print_preview(span);
  exit(EXIT_FAILURE);
}

void rt_err(const char *message, const char *help, const Location *span) {
  u_throw(303, &(RuntimeMessage){303, "RuntimeError", message, help}, span);
}
