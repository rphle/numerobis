#ifndef NUMEROBIS_STATE_H
#define NUMEROBIS_STATE_H

#include "color.h"

#include <SDL2/SDL.h>
#include <glib.h>
#include <stdbool.h>

extern SDL_Window *_window;
extern SDL_Renderer *_renderer;
extern GArray *_queue;
extern Color _bg;

extern int _mouse_x;
extern int _mouse_y;
extern bool _mouse_down;
extern bool _quit_requested;
extern bool _keys[SDL_NUM_SCANCODES];

extern double _scale;
extern double _tx;
extern double _ty;

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
      int x, y, w, h;
      bool filled;
    } rect;
    struct {
      int x, y, w, h, radius;
      bool filled;
    } rrect;
    struct {
      int x, y, radius;
      bool filled;
    } circle;
    struct {
      int x, y, rx, ry;
      bool filled;
    } ellipse;
    struct {
      int x1, y1, x2, y2;
      double thickness;
    } line;
    struct {
      SDL_Point *pts;
      int n;
      bool filled;
    } polygon;
    struct {
      int x, y, radius;
      float start, end;
      bool filled;
    } arc;
    struct {
      int x, y;
    } point;
    struct {
      int x, y, size, style;
      char *str, *font_path;
      double angle;
    } text;
  };
} DrawCmd;

inline void _set_color(Color c) {
  if (_renderer) {
    SDL_SetRenderDrawColor(_renderer, c.r, c.g, c.b, c.a);
  }
}

void _ensure_queue(void);
void _update_input_state(void);

void _cleanup_state(void);

#endif
