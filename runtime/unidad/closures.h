#ifndef UNIDAD_CLOSURES_H
#define UNIDAD_CLOSURES_H

#include <stdlib.h>
#include "values.h"

#define U_UNPACK_ENV(type) type *_e = (type *)__env;

#define U_SHADOW_VAR(name) Value *name = _e->name;

#define U_UNPACK_ARG(name, i) Value *name = __args[i];

#define U_UNPACK_OPT_ARG(name, i, default) Value *name = __args[i] ? __args[i] : default;

#define U_NEW_CLOSURE(impl, env_type, ...)                                     \
  closure__init__(impl,                                                        \
                  closure_capture(sizeof(env_type), &(env_type){__VA_ARGS__}))

void *closure_capture(size_t size, void *stack_env);

Value *closure__init__(Value *(*func)(void *, Value **), void *env);

Value *closure__call__(Value *callee, Value **args);

#endif
