#include "../../constants.h"
#include "../../extern.h"
#include "../../libs/gc_stb_ds.h"
#include "../../types/bool.h"
#include "../../types/number.h"
#include "../../units/units.h"
#include "../../utils/utils.h"
#include "../../values.h"
#include "fonts.h"
#include "primitives.h"
#include "state.h"

#include <SDL2/SDL.h>
#include <SDL2/SDL_thread.h>
#include <SDL2/SDL_timer.h>
#include <SDL2/SDL_ttf.h>
#include <gc.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>

static inline int _tx_x(double x) { return (int)((x * _scale)) + _tx; }
static inline int _tx_y(double y) { return (int)((y * _scale)) + _ty; }
static inline int _tx_dim(double dim) { return (int)(dim * _scale); }
volatile Uint8 *audio_pos; // global pointer to the audio buffer to be played
volatile Uint32 audio_len; // remaining length of the sample we have to play
static Uint32 wav_length;  // length of our sample
static Uint8 *wav_buffer;  // buffer containing our audio file
static SDL_AudioSpec wav_spec; // the specs of our piece of music

static inline bool _arg_filled(Value v) {
  return v.type != VALUE_EMPTY ? _bool(v) : true;
}

static inline Color _arg_color(Value v) {
  return v.type != VALUE_EMPTY ? _parse_color(_str(v)) : COLOR_BLACK;
}

static int _parse_style_list(Value style_val) {
  if (style_val.type != VALUE_LIST)
    return TTF_STYLE_NORMAL;
  Value *arr = style_val.list->items;
  int flags = TTF_STYLE_NORMAL;
  for (unsigned int i = 0; i < arrlen(arr); i++) {
    Value item = arr[i];
    if (item.type != VALUE_STR || !item.str)
      continue;
    const char *s = item.str;
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

/* init!(width: Int, height: Int): Int */
static Value numerobis_builtin_graphics_init(Value *args) {
  int w = (int)_i64(args[1]);
  int h = (int)_i64(args[2]);

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
  return int__init__(1, U_ONE);
}

/* set_bg!(color: Str) */
static Value numerobis_builtin_set_bg(Value *args) {
  _bg = _parse_color(_str(args[1]));
  return NONE;
}

/* set_title!(title: Str) */
static Value numerobis_builtin_set_title(Value *args) {
  if (_window)
    SDL_SetWindowTitle(_window, _str(args[1]));
  return NONE;
}

/* set_font!(name: Str) — e.g. "Arial", "DejaVu Sans" */
static Value numerobis_builtin_set_font(Value *args) {
  const char *path = _resolve_font_name(_str(args[1]));
  if (!path)
    return int__init__(0, U_ONE);
  _font_path = path;
  return int__init__(1, U_ONE);
}

/* rect!(x, y, w, h, color, filled) */
static Value numerobis_builtin_rect(Value *args) {
  DrawCmd cmd = {.kind = CMD_RECT,
                 .color = _arg_color(args[5]),
                 .rect = {_tx_x(_f64(args[1])), _tx_y(_f64(args[2])),
                          _tx_dim(_f64(args[3])), _tx_dim(_f64(args[4])),
                          _arg_filled(args[6])}};
  arrput(_queue, cmd);
  return NONE;
}

/* rounded_rect!(x, y, w, h, radius, color, filled) */
static Value numerobis_builtin_rounded_rect(Value *args) {
  DrawCmd cmd = {.kind = CMD_ROUNDED_RECT,
                 .color = _arg_color(args[6]),
                 .rrect = {_tx_x(_f64(args[1])), _tx_y(_f64(args[2])),
                           _tx_dim(_f64(args[3])), _tx_dim(_f64(args[4])),
                           _tx_dim(_f64(args[5])), _arg_filled(args[7])}};
  arrput(_queue, cmd);
  return NONE;
}

/* circle!(x, y, radius, color, filled) */
static Value numerobis_builtin_circle(Value *args) {
  DrawCmd cmd = {.kind = CMD_CIRCLE,
                 .color = _arg_color(args[4]),
                 .circle = {_tx_x(_f64(args[1])), _tx_y(_f64(args[2])),
                            _tx_dim(_f64(args[3])), _arg_filled(args[5])}};
  arrput(_queue, cmd);
  return NONE;
}

/* ellipse!(x, y, rx, ry, color, filled) */
static Value numerobis_builtin_ellipse(Value *args) {
  DrawCmd cmd = {.kind = CMD_ELLIPSE,
                 .color = _arg_color(args[5]),
                 .ellipse = {_tx_x(_f64(args[1])), _tx_y(_f64(args[2])),
                             _tx_dim(_f64(args[3])), _tx_dim(_f64(args[4])),
                             _arg_filled(args[6])}};
  arrput(_queue, cmd);
  return NONE;
}

/* line!(x1, y1, x2, y2, color, thickness) */
static Value numerobis_builtin_line(Value *args) {
  double thickness = args[6].type != VALUE_EMPTY ? _f64(args[6]) : 1.0;
  DrawCmd cmd = {.kind = CMD_LINE,
                 .color = _arg_color(args[5]),
                 .line = {_tx_x(_f64(args[1])), _tx_y(_f64(args[2])),
                          _tx_x(_f64(args[3])), _tx_y(_f64(args[4])),
                          thickness}};
  arrput(_queue, cmd);
  return NONE;
}

/* polygon!(points: List[Num], color, filled) */
static Value numerobis_builtin_polygon(Value *args) {
  Value *arr = args[1].list->items;
  int n = (int)(arrlen(arr) / 2);
  SDL_Point *pts = GC_MALLOC(n * sizeof(SDL_Point));

  for (int i = 0; i < n; i++) {
    double px = _f64(arr[i * 2]);
    double py = _f64(arr[i * 2 + 1]);
    pts[i].x = _tx_x(px);
    pts[i].y = _tx_y(py);
  }

  DrawCmd cmd = {.kind = CMD_POLYGON,
                 .color = _arg_color(args[2]),
                 .polygon = {pts, n, _arg_filled(args[3])}};
  arrput(_queue, cmd);
  return NONE;
}

/* arc!(x, y, radius, start, end, color, filled) */
static Value numerobis_builtin_arc(Value *args) {
  DrawCmd cmd = {.kind = CMD_ARC,
                 .color = _arg_color(args[6]),
                 .arc = {_tx_x(_f64(args[1])), _tx_y(_f64(args[2])),
                         _tx_dim(_f64(args[3])), (float)_f64(args[4]),
                         (float)_f64(args[5]), _arg_filled(args[7])}};
  arrput(_queue, cmd);
  return NONE;
}

/* point!(x, y, color) */
static Value numerobis_builtin_point(Value *args) {
  DrawCmd cmd = {.kind = CMD_POINT,
                 .color = _arg_color(args[3]),
                 .point = {_tx_x(_f64(args[1])), _tx_y(_f64(args[2]))}};
  arrput(_queue, cmd);
  return NONE;
}

/* text!(x, y, content, size, color, style: List[Str], font: Str, angle: Num) */
static Value numerobis_builtin_text(Value *args) {

  const char *font_arg = args[7].type != VALUE_EMPTY ? _str(args[7]) : NULL;
  const char *font_path =
      font_arg ? _resolve_font_name(font_arg) : _default_font();
  if (!font_path)
    font_path = _default_font();

  double angle_arg = args[8].type != VALUE_EMPTY ? _f64(args[8]) : 0.0;
  int style_arg = args[6].type != VALUE_EMPTY ? _parse_style_list(args[6])
                                              : TTF_STYLE_NORMAL;
  int size_arg = args[4].type != VALUE_EMPTY ? _tx_dim(_f64(args[4])) : 16;

  DrawCmd cmd = {
      .kind = CMD_TEXT,
      .color = _arg_color(args[5]),
      .text =
          {
              .x = _tx_x(_f64(args[1])),
              .y = _tx_y(_f64(args[2])),
              .str = GC_STRDUP(_str(args[3])),
              .size = size_arg,
              .style = style_arg,
              .font_path = font_path ? GC_STRDUP(font_path) : NULL,
              .angle = angle_arg,
          },
  };
  arrput(_queue, cmd);
  return NONE;
}

static Value numerobis_builtin_blit(Value *args) {
  (void)args;
  if (!_renderer || !_queue)
    return NONE;

  _set_color(_bg);
  SDL_RenderClear(_renderer);

  for (unsigned int qi = 0; qi < arrlen(_queue); qi++) {
    DrawCmd *c = &_queue[qi];
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
  if (arrlen(_queue) > 0) {
    memset(_queue, 0, arrlen(_queue) * sizeof(DrawCmd));
    arrsetlen(_queue, 0);
  }
  return NONE;
}

/* mouse_down!(): Bool */
static Value numerobis_builtin_mouse_down(Value *args) {
  _update_input_state();
  return bool__init__(_mouse_down);
}

/* mouse_x!(): Num */
static Value numerobis_builtin_mouse_x(Value *args) {
  _update_input_state();
  return num__init__(_mouse_x, U_ONE);
}

/* mouse_y!(): Num */
static Value numerobis_builtin_mouse_y(Value *args) {
  _update_input_state();
  return num__init__(_mouse_y, U_ONE);
}

/* mouse_vx!(): Num */
static Value numerobis_builtin_mouse_vx(Value *args) {
  _update_input_state();
  return num__init__(((_mouse_x / _scale) - _tx), U_ONE);
}

/* mouse_vy!(): Num */
static Value numerobis_builtin_mouse_vy(Value *args) {
  _update_input_state();
  return num__init__(((_mouse_y / _scale) - _ty), U_ONE);
}

/* quit_requested!(): Bool */
static Value numerobis_builtin_quit_requested(Value *args) {
  _update_input_state();
  return bool__init__(_quit_requested);
}

/* key_pressed!(key_name: Str): Bool */
static Value numerobis_builtin_key_pressed(Value *args) {
  _update_input_state();
  const char *key_name = _str(args[1]);
  SDL_Scancode code = SDL_GetScancodeFromName(key_name);
  if (code == SDL_SCANCODE_UNKNOWN) {
    return bool__init__(false);
  }
  return bool__init__(_keys[code]);
}

/* set_scale!(value: Num, pixels: Num = 1): None */
static Value numerobis_builtin_set_scale(Value *args) {
  double value = _f64(args[1]);
  double pixels = args[2].type != VALUE_EMPTY ? _f64(args[2]) : 1;
  _scale = pixels / value;
  return NONE;
}

/* set_origin!(x: Num, y: Num): None */
static Value numerobis_builtin_set_origin(Value *args) {
  _tx = _f64(args[1]);
  _ty = _f64(args[2]);
  return NONE;
}

void audio_callback(void *userdata, Uint8 *stream, int len) {
  if (audio_len == 0) {
    return;
  }
  len = (len > audio_len ? audio_len : len);
  SDL_memcpy(stream, audio_pos, len);
  audio_pos += len;
  audio_len -= len;
}

int audio_wait_thread(void *arg) {
  SDL_LoadWAV(arg, &wav_spec, &wav_buffer, &wav_length);

  wav_spec.callback = audio_callback;
  wav_spec.userdata = NULL;
  audio_pos = wav_buffer;
  audio_len = wav_length;

  /* Open the audio device */
  if (SDL_OpenAudio(&wav_spec, NULL) < 0) {
    fprintf(stderr, "Couldn't open audio: %s\n", SDL_GetError());
    exit(-1);
  }

  SDL_PauseAudio(0);
  while (audio_len > 0) {
    SDL_Delay(25);
  }

  /* Shut everything down */
  SDL_CloseAudio();
  SDL_FreeWAV(wav_buffer);

  return 1;
}

static Value numerobis_builtin_play_sound(Value *args) {
  sds path = _str(args[1]);
  audio_len = 0;
  SDL_Delay(60);

  /* Start playing */
  SDL_Thread *thread = SDL_CreateThread(audio_wait_thread, "audio_wait", path);
  SDL_DetachThread(thread);

  return NONE;
}

__attribute__((constructor)) void numerobis_graphics_register_builtins(void) {
  u_extern_register("init", numerobis_builtin_graphics_init);
  u_extern_register("set__bg", numerobis_builtin_set_bg);
  u_extern_register("set__title", numerobis_builtin_set_title);
  u_extern_register("set__font", numerobis_builtin_set_font);
  u_extern_register("rect", numerobis_builtin_rect);
  u_extern_register("rounded__rect", numerobis_builtin_rounded_rect);
  u_extern_register("circle", numerobis_builtin_circle);
  u_extern_register("ellipse", numerobis_builtin_ellipse);
  u_extern_register("line", numerobis_builtin_line);
  u_extern_register("polygon", numerobis_builtin_polygon);
  u_extern_register("arc", numerobis_builtin_arc);
  u_extern_register("point", numerobis_builtin_point);
  u_extern_register("text", numerobis_builtin_text);
  u_extern_register("blit", numerobis_builtin_blit);
  u_extern_register("mouse__down", numerobis_builtin_mouse_down);
  u_extern_register("mouse__x", numerobis_builtin_mouse_x);
  u_extern_register("mouse__y", numerobis_builtin_mouse_y);
  u_extern_register("mouse__vx", numerobis_builtin_mouse_vx);
  u_extern_register("mouse__vy", numerobis_builtin_mouse_vy);
  u_extern_register("quit__requested", numerobis_builtin_quit_requested);
  u_extern_register("key__pressed", numerobis_builtin_key_pressed);
  u_extern_register("set__scale", numerobis_builtin_set_scale);
  u_extern_register("set__origin", numerobis_builtin_set_origin);
  u_extern_register("play__sound", numerobis_builtin_play_sound);
}

__attribute__((destructor)) void numerobis_graphics_cleanup(void) {
  _cleanup_fonts();
  _cleanup_state();

  if (TTF_WasInit()) {
    TTF_Quit();
  }
  if (SDL_WasInit(SDL_INIT_VIDEO)) {
    SDL_Quit();
  }
}
