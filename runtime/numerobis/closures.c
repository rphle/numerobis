#include "closures.h"
#include "values.h"

#include <gc.h>
#include <string.h>

Value closure__init__(Value (*func)(void *, Value *), void *env,
                      Value bound_arg) {
  Closure *c = (Closure *)GC_MALLOC(sizeof(Closure));
  c->func = func;
  c->env = env;
  c->bound_arg = bound_arg;

  Value v;
  v.type = VALUE_CLOSURE;
  v.closure = c;
  return v;
}

void *closure_capture(size_t size, void *stack_env) {
  if (size == 0)
    return NULL;
  void *heap_env = GC_MALLOC(size);
  memcpy(heap_env, stack_env, size);
  return heap_env;
}
