#include "closures.h"
#include "values.h"
#include <glib.h>
#include <stdlib.h>
#include <string.h>

_Thread_local ClosureFreeNode *_closure_free_list = NULL;

Value closure__init__(Value (*func)(void *, Value *), void *env,
                      Value *first_arg) {
  Closure *c = closure_slab_alloc();
  c->func = func;
  c->env = env;
  c->first_arg = first_arg;
  Value v;
  v.type = VALUE_CLOSURE;
  v.closure = c;
  return v;
}

void _closure_slab_refill(void) {
  // each slot must be at least sizeof(Closure) so that it can hold a Closure
  // AND be reused as a ClosureFreeNode
  _Static_assert(sizeof(Closure) >= sizeof(ClosureFreeNode),
                 "Closure must be at least as large as ClosureFreeNode");

  Closure *block = (Closure *)g_malloc(CLOSURE_SLAB_CHUNK * sizeof(Closure));

  for (int i = CLOSURE_SLAB_CHUNK - 1; i >= 0; i--) {
    ClosureFreeNode *node = (ClosureFreeNode *)&block[i];
    node->next = _closure_free_list;
    _closure_free_list = node;
  }
}

void *closure_capture(size_t size, void *stack_env) {
  if (size == 0)
    return NULL;
  void *heap_env = g_malloc(size);
  memcpy(heap_env, stack_env, size);
  return heap_env;
}
