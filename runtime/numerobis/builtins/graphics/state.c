#include "state.h"

#include <gc.h>

SDL_Window *_window = NULL;
SDL_Renderer *_renderer = NULL;
GArray *_queue = NULL;
Color _bg = {0, 0, 0, 255};

void _ensure_queue(void) {
  if (!_queue)
    _queue = g_array_new(FALSE, FALSE, sizeof(DrawCmd));
}
