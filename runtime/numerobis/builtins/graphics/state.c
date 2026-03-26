#include "state.h"

#include <gc.h>

SDL_Window *_window = NULL;
SDL_Renderer *_renderer = NULL;
GArray *_queue = NULL;
Color _bg = {0, 0, 0, 255};

gint32 _mouse_x = 0;
gint32 _mouse_y = 0;
gboolean _mouse_down = FALSE;
gboolean _quit_requested = FALSE;

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
    }
  }
}
