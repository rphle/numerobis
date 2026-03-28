#include "state.h"
#include "glibconfig.h"

#include <gc.h>

SDL_Window *_window = NULL;
SDL_Renderer *_renderer = NULL;
GArray *_queue = NULL;
Color _bg = {0, 0, 0, 255};

gint32 _mouse_x = 0;
gint32 _mouse_y = 0;
gboolean _mouse_down = FALSE;
gboolean _quit_requested = FALSE;
gboolean _keys[SDL_NUM_SCANCODES] = {FALSE};

gdouble _scale = 1.0;
gdouble _tx = 0.0;
gdouble _ty = 0.0;

void _ensure_queue(void) {
  if (!_queue)
    _queue = g_array_new(FALSE, FALSE, sizeof(DrawCmd));
}

void _update_input_state(void) {
  SDL_Event event;
  while (SDL_PollEvent(&event)) {
    switch (event.type) {
    case SDL_QUIT:
      _quit_requested = TRUE;
      break;
    case SDL_MOUSEMOTION:
      _mouse_x = event.motion.x;
      _mouse_y = event.motion.y;
      break;
    case SDL_MOUSEBUTTONDOWN:
      if (event.button.button == SDL_BUTTON_LEFT)
        _mouse_down = TRUE;
      break;
    case SDL_MOUSEBUTTONUP:
      if (event.button.button == SDL_BUTTON_LEFT)
        _mouse_down = FALSE;
      break;
    case SDL_KEYDOWN:
      if (event.key.keysym.scancode < SDL_NUM_SCANCODES)
        _keys[event.key.keysym.scancode] = TRUE;
      break;
    case SDL_KEYUP:
      if (event.key.keysym.scancode < SDL_NUM_SCANCODES)
        _keys[event.key.keysym.scancode] = FALSE;
      break;
    }
  }
}

void _cleanup_state(void) {
  if (_queue) {
    g_array_unref(_queue);
    _queue = NULL;
  }
  if (_renderer) {
    SDL_DestroyRenderer(_renderer);
    _renderer = NULL;
  }
  if (_window) {
    SDL_DestroyWindow(_window);
    _window = NULL;
  }
}
