#include "values.h"
#include <glib.h>
#include <stdlib.h>

void *closure_capture(size_t size, void *stack_env) {
  if (size == 0)
    return NULL;
  void *heap_env = g_malloc(size);
  memcpy(heap_env, stack_env, size);
  return heap_env;
}

Value *closure__init__(Value *(*func)(void *, Value **), void *env) {
  Value *v = g_malloc(sizeof(Value));
  v->type = VALUE_CLOSURE;
  v->closure = g_malloc(sizeof(Closure));
  v->closure->func = func;
  v->closure->env = env;
  return v;
}

Value *closure__call__(Value *callee, Value **args) {
  return callee->closure->func(callee->closure->env, args);
}
