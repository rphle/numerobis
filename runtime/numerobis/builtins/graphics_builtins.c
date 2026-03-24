#include "graphics_builtins.h"
#include "../extern.h"
#include "../types/number.h"
#include "../units/units.h"
#include "../utils/utils.h"
#include "../values.h"
#include "graphics/fonts.h"
#include "graphics/primitives.h"
#include "graphics/state.h"

#include <SDL2/SDL.h>
#include <SDL2/SDL_ttf.h>
#include <gc.h>
#include <glib.h>
#include <stdio.h>
#include <string.h>

static gint32 _parse_style_list(Value style_val) {
  if (style_val.type != VALUE_LIST)
    return TTF_STYLE_NORMAL;
  GArray *arr = style_val.list;
  gint32 flags = TTF_STYLE_NORMAL;
  for (guint i = 0; i < arr->len; i++) {
    Value item = g_array_index(arr, Value, i);
    if (item.type != VALUE_STR || !item.str)
      continue;
    const gchar *s = item.str->str;
    if (strcmp(s, "bold") == 0)
      flags |= TTF_STYLE_BOLD;
    if (strcmp(s, "italic") == 0)
      flags |= TTF_STYLE_ITALIC;
    if (strcmp(s, "underline") == 0)
      flags |= TTF_STYLE_UNDERLINE;
    if (strcmp(s, "strikethrough") == 0)
      flags |= TTF_STYLE_STRIKETHROUGH;
  }
  return flags;
}

static inline Value _none(void) {
  return (Value){.type = VALUE_NONE, .none = NULL};
}

/* init!(width: Int, height: Int): Int */
static Value numerobis_builtin_graphics_init(Value *args) {
  gint32 w = (gint32)_i64(args, 1);
  gint32 h = (gint32)_i64(args, 2);

  if (SDL_Init(SDL_INIT_VIDEO) != 0) {
    fprintf(stderr, "graphics: SDL_Init: %s\n", SDL_GetError());
    return int__init__(0, U_ONE);
  }
  if (TTF_Init() != 0) {
    fprintf(stderr, "graphics: TTF_Init: %s\n", TTF_GetError());
    return int__init__(0, U_ONE);
  }
  _window = SDL_CreateWindow("Numerobis", SDL_WINDOWPOS_CENTERED,
                             SDL_WINDOWPOS_CENTERED, w, h, SDL_WINDOW_SHOWN);
  if (!_window) {
    fprintf(stderr, "graphics: SDL_CreateWindow: %s\n", SDL_GetError());
    return int__init__(0, U_ONE);
  }
  _renderer = SDL_CreateRenderer(
      _window, -1, SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC);
  if (!_renderer) {
    fprintf(stderr, "graphics: SDL_CreateRenderer: %s\n", SDL_GetError());
    return int__init__(0, U_ONE);
  }
  SDL_SetRenderDrawBlendMode(_renderer, SDL_BLENDMODE_BLEND);
  _ensure_queue();
  return int__init__(1, U_ONE);
}

/* set_bg!(color: Str) */
static Value numerobis_builtin_set_bg(Value *args) {
  _bg = _parse_color(_str(args, 1));
  return _none();
}

/* set_title!(title: Str) */
static Value numerobis_builtin_set_title(Value *args) {
  if (_window)
    SDL_SetWindowTitle(_window, _str(args, 1));
  return _none();
}

/* set_font!(name: Str) — e.g. "Arial", "DejaVu Sans" */
static Value numerobis_builtin_set_font(Value *args) {
  const gchar *path = _resolve_font_name(_str(args, 1));
  if (!path)
    return int__init__(0, U_ONE);
  _font_path = path;
  return int__init__(1, U_ONE);
}

/* rect!(x, y, w, h, color, filled) */
static Value numerobis_builtin_rect(Value *args) {
  _ensure_queue();
  DrawCmd cmd = {.kind = CMD_RECT,
                 .color = _parse_color(_str(args, 5)),
                 .rect = {(gint32)_i64(args, 1), (gint32)_i64(args, 2),
                          (gint32)_i64(args, 3), (gint32)_i64(args, 4),
                          _bool(args, 6)}};
  g_array_append_val(_queue, cmd);
  return _none();
}

/* rounded_rect!(x, y, w, h, radius, color, filled) */
static Value numerobis_builtin_rounded_rect(Value *args) {
  _ensure_queue();
  DrawCmd cmd = {.kind = CMD_ROUNDED_RECT,
                 .color = _parse_color(_str(args, 6)),
                 .rrect = {(gint32)_i64(args, 1), (gint32)_i64(args, 2),
                           (gint32)_i64(args, 3), (gint32)_i64(args, 4),
                           (gint32)_i64(args, 5), _bool(args, 7)}};
  g_array_append_val(_queue, cmd);
  return _none();
}

/* circle!(x, y, radius, color, filled) */
static Value numerobis_builtin_circle(Value *args) {
  _ensure_queue();
  DrawCmd cmd = {.kind = CMD_CIRCLE,
                 .color = _parse_color(_str(args, 4)),
                 .circle = {(gint32)_i64(args, 1), (gint32)_i64(args, 2),
                            (gint32)_i64(args, 3), _bool(args, 5)}};
  g_array_append_val(_queue, cmd);
  return _none();
}

/* ellipse!(x, y, rx, ry, color, filled) */
static Value numerobis_builtin_ellipse(Value *args) {
  _ensure_queue();
  DrawCmd cmd = {.kind = CMD_ELLIPSE,
                 .color = _parse_color(_str(args, 5)),
                 .ellipse = {(gint32)_i64(args, 1), (gint32)_i64(args, 2),
                             (gint32)_i64(args, 3), (gint32)_i64(args, 4),
                             _bool(args, 6)}};
  g_array_append_val(_queue, cmd);
  return _none();
}

/* line!(x1, y1, x2, y2, color, thickness) */
static Value numerobis_builtin_line(Value *args) {
  _ensure_queue();
  DrawCmd cmd = {.kind = CMD_LINE,
                 .color = _parse_color(_str(args, 5)),
                 .line = {(gint32)_i64(args, 1), (gint32)_i64(args, 2),
                          (gint32)_i64(args, 3), (gint32)_i64(args, 4),
                          _f64(args, 6)}};
  g_array_append_val(_queue, cmd);
  return _none();
}

/* polygon!(points: List[Int], color, filled) */
static Value numerobis_builtin_polygon(Value *args) {
  _ensure_queue();
  GArray *arr = args[1].list;
  gint32 n = (gint32)(arr->len / 2);
  SDL_Point *pts = GC_MALLOC(n * sizeof(SDL_Point));
  for (gint32 i = 0; i < n; i++) {
    pts[i].x = (int)g_array_index(arr, Value, i * 2).number.i64;
    pts[i].y = (int)g_array_index(arr, Value, i * 2 + 1).number.i64;
  }
  DrawCmd cmd = {.kind = CMD_POLYGON,
                 .color = _parse_color(_str(args, 2)),
                 .polygon = {pts, n, _bool(args, 3)}};
  g_array_append_val(_queue, cmd);
  return _none();
}

/* arc!(x, y, radius, start, end, color, filled) */
static Value numerobis_builtin_arc(Value *args) {
  _ensure_queue();
  DrawCmd cmd = {.kind = CMD_ARC,
                 .color = _parse_color(_str(args, 6)),
                 .arc = {(gint32)_i64(args, 1), (gint32)_i64(args, 2),
                         (gint32)_i64(args, 3), (gfloat)_f64(args, 4),
                         (gfloat)_f64(args, 5), _bool(args, 7)}};
  g_array_append_val(_queue, cmd);
  return _none();
}

/* point!(x, y, color) */
static Value numerobis_builtin_point(Value *args) {
  _ensure_queue();
  DrawCmd cmd = {.kind = CMD_POINT,
                 .color = _parse_color(_str(args, 3)),
                 .point = {(gint32)_i64(args, 1), (gint32)_i64(args, 2)}};
  g_array_append_val(_queue, cmd);
  return _none();
}

/* text!(x, y, content, size, color, style: List[Str], font: Str, angle: Float)
 */
static Value numerobis_builtin_text(Value *args) {
  _ensure_queue();

  const gchar *font_arg = _str(args, 7);
  const gchar *font_path =
      (font_arg && *font_arg) ? _resolve_font_name(font_arg) : _default_font();
  if (!font_path)
    font_path = _default_font();

  DrawCmd cmd = {
      .kind = CMD_TEXT,
      .color = _parse_color(_str(args, 5)),
      .text =
          {
              .x = (gint32)_i64(args, 1),
              .y = (gint32)_i64(args, 2),
              .str = GC_STRDUP(_str(args, 3)),
              .size = (gint32)_i64(args, 4),
              .style = _parse_style_list(args[6]),
              .font_path = font_path ? GC_STRDUP(font_path) : NULL,
              .angle = _f64(args, 8),
          },
  };
  g_array_append_val(_queue, cmd);
  return _none();
}

static Value numerobis_builtin_blit(Value *args) {
  (void)args;
  if (!_renderer || !_queue)
    return _none();

  _set_color(_bg);
  SDL_RenderClear(_renderer);

  for (guint qi = 0; qi < _queue->len; qi++) {
    DrawCmd *c = &g_array_index(_queue, DrawCmd, qi);
    _set_color(c->color);

    switch (c->kind) {
    case CMD_RECT: {
      SDL_Rect r = {c->rect.x, c->rect.y, c->rect.w, c->rect.h};
      if (c->rect.filled)
        SDL_RenderFillRect(_renderer, &r);
      else
        SDL_RenderDrawRect(_renderer, &r);
      break;
    }
    case CMD_ROUNDED_RECT:
      _prim_rounded_rect(c->rrect.x, c->rrect.y, c->rrect.w, c->rrect.h,
                         c->rrect.radius, c->rrect.filled);
      break;
    case CMD_CIRCLE:
      _prim_circle(c->circle.x, c->circle.y, c->circle.radius,
                   c->circle.filled);
      break;
    case CMD_ELLIPSE:
      _prim_ellipse(c->ellipse.x, c->ellipse.y, c->ellipse.rx, c->ellipse.ry,
                    c->ellipse.filled);
      break;
    case CMD_LINE:
      _prim_thick_line(c->line.x1, c->line.y1, c->line.x2, c->line.y2,
                       c->line.thickness);
      break;
    case CMD_POLYGON:
      _prim_polygon(c->polygon.pts, c->polygon.n, c->polygon.filled);
      break;
    case CMD_ARC:
      _prim_arc(c->arc.x, c->arc.y, c->arc.radius, c->arc.start, c->arc.end,
                c->arc.filled);
      break;
    case CMD_POINT:
      SDL_RenderDrawPoint(_renderer, c->point.x, c->point.y);
      break;
    case CMD_TEXT: {
      if (!c->text.font_path) {
        fprintf(stderr, "graphics: no font available\n");
        break;
      }
      TTF_Font *font =
          _get_font(c->text.font_path, c->text.size, c->text.style);
      if (!font)
        break;

      SDL_Color sdl_c = {c->color.r, c->color.g, c->color.b, c->color.a};
      SDL_Surface *surf = TTF_RenderUTF8_Blended(font, c->text.str, sdl_c);
      if (!surf)
        break;

      SDL_Texture *tex = SDL_CreateTextureFromSurface(_renderer, surf);
      SDL_Rect dst = {c->text.x, c->text.y, surf->w, surf->h};
      SDL_FreeSurface(surf);

      if (tex) {
        if (c->text.angle != 0.0) {
          SDL_Point origin = {0, 0};
          SDL_RenderCopyEx(_renderer, tex, NULL, &dst, c->text.angle, &origin,
                           SDL_FLIP_NONE);
        } else {
          SDL_RenderCopy(_renderer, tex, NULL, &dst);
        }
        SDL_DestroyTexture(tex);
      }
      break;
    }
    }
  }

  SDL_RenderPresent(_renderer);
  g_array_set_size(_queue, 0);
  return _none();
}

void numerobis_graphics_register_builtins(void) {
  u_extern_register("init", numerobis_builtin_graphics_init);
  u_extern_register("set_bg", numerobis_builtin_set_bg);
  u_extern_register("set_title", numerobis_builtin_set_title);
  u_extern_register("set_font", numerobis_builtin_set_font);
  u_extern_register("rect", numerobis_builtin_rect);
  u_extern_register("rounded_rect", numerobis_builtin_rounded_rect);
  u_extern_register("circle", numerobis_builtin_circle);
  u_extern_register("ellipse", numerobis_builtin_ellipse);
  u_extern_register("line", numerobis_builtin_line);
  u_extern_register("polygon", numerobis_builtin_polygon);
  u_extern_register("arc", numerobis_builtin_arc);
  u_extern_register("point", numerobis_builtin_point);
  u_extern_register("text", numerobis_builtin_text);
  u_extern_register("blit", numerobis_builtin_blit);
}
