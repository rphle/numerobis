#ifndef NUMEROBIS_STATE_H
#define NUMEROBIS_STATE_H

#include "color.h"

#include <SDL2/SDL.h>
#include <glib.h>

extern SDL_Window *_window;
extern SDL_Renderer *_renderer;
extern GArray *_queue;
extern Color _bg;

typedef enum {
  CMD_RECT,
  CMD_ROUNDED_RECT,
  CMD_CIRCLE,
  CMD_ELLIPSE,
  CMD_LINE,
  CMD_POLYGON,
  CMD_ARC,
  CMD_POINT,
  CMD_TEXT,
} CmdKind;

typedef struct {
  CmdKind kind;
  Color color;
  union {
    struct {
      gint32 x, y, w, h;
      gboolean filled;
    } rect;
    struct {
      gint32 x, y, w, h, radius;
      gboolean filled;
    } rrect;
    struct {
      gint32 x, y, radius;
      gboolean filled;
    } circle;
    struct {
      gint32 x, y, rx, ry;
      gboolean filled;
    } ellipse;
    struct {
      gint32 x1, y1, x2, y2;
      gdouble thickness;
    } line;
    struct {
      SDL_Point *pts;
      gint32 n;
      gboolean filled;
    } polygon;
    struct {
      gint32 x, y, radius;
      gfloat start, end;
      gboolean filled;
    } arc;
    struct {
      gint32 x, y;
    } point;
    struct {
      gint32 x, y, size, style;
      gchar *str, *font_path;
      gdouble angle;
    } text;
  };
} DrawCmd;

inline void _set_color(Color c) {
  if (_renderer) {
    SDL_SetRenderDrawColor(_renderer, c.r, c.g, c.b, c.a);
  }
}

void _ensure_queue(void);

#endif
