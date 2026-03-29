#ifndef NUMEROBIS_CLOSURES_H
#define NUMEROBIS_CLOSURES_H

#include "units/units.h"
#include "values.h"

#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#define U_UNPACK_ENV(type) type *_e = (type *)__env;
#define U_SHADOW_VAR(name) Value name = _e->name;
#define U_UNPACK_ARG(name, i) Value name = __args[i];
#define U_UNPACK_OPT_ARG(name, i, def)                                         \
  Value name = (__args[i].type != VALUE_NONE ? __args[i] : (def));

#define CLOSURE_SLAB_CHUNK 256

typedef struct ClosureFreeNode {
  struct ClosureFreeNode *next;
} ClosureFreeNode;

extern _Thread_local ClosureFreeNode *_closure_free_list;

static inline Closure *closure_slab_alloc(void);

void _closure_slab_refill(void);

static inline Closure *closure_slab_alloc(void) {
  if (__builtin_expect(_closure_free_list == NULL, 0))
    _closure_slab_refill();
  ClosureFreeNode *node = _closure_free_list;
  _closure_free_list = node->next;
  return (Closure *)node;
}

void *closure_capture(size_t size, void *stack_env);

Value closure__init__(Value (*func)(void *, Value *), void *env,
                      Value bound_arg);

#define U_NEW_CLOSURE(impl, env_type, ...)                                     \
  closure__init__(                                                             \
      impl, closure_capture(sizeof(env_type), &(env_type){__VA_ARGS__}), NONE)

static inline bool _is_plain_int(Value v) {
  return v.type == VALUE_NUMBER && v.number.kind == NUM_INT64 &&
         v.number.unit == NUMEROBIS_UNIT_ONE_HASH;
}

#define _FAST_INT_BINOP(a, b, op_i64, op_fallback)                             \
  ({                                                                           \
    Value _fa = (a), _fb = (b);                                                \
    __builtin_expect(_is_plain_int(_fa) & _is_plain_int(_fb), 1)               \
        ? (Value){.type = VALUE_NUMBER,                                        \
                  .number = {.kind = NUM_INT64,                                \
                             .unit = NUMEROBIS_UNIT_ONE_HASH,                  \
                             .i64 = _fa.number.i64 op_i64 _fb.number.i64}}     \
        : (op_fallback)(_fa, _fb);                                             \
  })

#define FAST_ADD(a, b) _FAST_INT_BINOP(a, b, +, __add__)
#define FAST_SUB(a, b) _FAST_INT_BINOP(a, b, -, __sub__)
#define FAST_MUL(a, b) _FAST_INT_BINOP(a, b, *, __mul__)

#define _FAST_CMP_BOOL(a, b, int_op, fallback_fn)                              \
  ({                                                                           \
    Value _fa = (a), _fb = (b);                                                \
    __builtin_expect(_is_plain_int(_fa) & _is_plain_int(_fb), 1)               \
        ? (_fa.number.i64 int_op _fb.number.i64)                               \
        : __cbool__(fallback_fn(_fa, _fb));                                    \
  })

#define FAST_LE_BOOL(a, b) _FAST_CMP_BOOL(a, b, <=, __le__)
#define FAST_LT_BOOL(a, b) _FAST_CMP_BOOL(a, b, <, __lt__)
#define FAST_EQ_BOOL(a, b) _FAST_CMP_BOOL(a, b, ==, __eq__)

#endif
