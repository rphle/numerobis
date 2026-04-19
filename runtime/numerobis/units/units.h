#ifndef NUMEROBIS_UNITS_H
#define NUMEROBIS_UNITS_H

#include "../libs/sds.h"
#include "../libs/bdwgc/include/gc.h"

#include <stdbool.h>
#include <stdint.h>

#define UMAP_INIT_CAP 4096
#define UMAP_LOAD_NUM 3
#define UMAP_LOAD_DEN 4

typedef struct {
  uint64_t key; // 0 == empty slot
  void *val;
} UMapSlot;

typedef struct {
  UMapSlot *slots;
  uint32_t cap; // always power of two
  uint32_t used;
} UMap;

static inline void umap_init(UMap *m, uint32_t cap) {
  m->slots = (UMapSlot *)GC_MALLOC(cap * sizeof(UMapSlot));
  m->cap = cap;
  m->used = 0;
}

static inline void umap_free(UMap *m) {
  m->slots = NULL;
  m->cap = m->used = 0;
}

static inline void umap_insert_raw(UMap *m, uint64_t key, void *val);

static inline void umap_grow(UMap *m) {
  uint32_t old_cap = m->cap;
  UMapSlot *old_slots = m->slots;
  uint32_t new_cap = old_cap * 2;

  m->slots = (UMapSlot *)GC_MALLOC(new_cap * sizeof(UMapSlot));
  m->cap = new_cap;
  m->used = 0;

  for (uint32_t i = 0; i < old_cap; i++) {
    if (old_slots[i].key != 0)
      umap_insert_raw(m, old_slots[i].key, old_slots[i].val);
  }
}

static inline void umap_insert_raw(UMap *m, uint64_t key, void *val) {
  uint32_t mask = m->cap - 1;
  uint32_t idx = (uint32_t)key & mask;
  while (m->slots[idx].key != 0 && m->slots[idx].key != key)
    idx = (idx + 1) & mask;
  if (m->slots[idx].key == 0)
    m->used++;
  m->slots[idx].key = key;
  m->slots[idx].val = val;
}

static inline void umap_insert(UMap *m, uint64_t key, void *val) {
  if (m->used * UMAP_LOAD_DEN >= m->cap * UMAP_LOAD_NUM)
    umap_grow(m);
  umap_insert_raw(m, key, val);
}

static inline void *umap_lookup(const UMap *m, uint64_t key) {
  uint32_t mask = m->cap - 1;
  uint32_t idx = (uint32_t)key & mask;
  while (m->slots[idx].key != 0) {
    if (m->slots[idx].key == key)
      return m->slots[idx].val;
    idx = (idx + 1) & mask;
  }
  return NULL;
}

static inline bool umap_contains(const UMap *m, uint64_t key) {
  return umap_lookup(m, key) != NULL;
}

#define UNIT_CACHE_BITS 9
#define UNIT_CACHE_SIZE (1u << UNIT_CACHE_BITS)
#define UNIT_CACHE_MASK (UNIT_CACHE_SIZE - 1u)

typedef struct {
  uint64_t hash;
  void *unit;
} UnitCacheSlot;

extern _Thread_local UnitCacheSlot _unit_tls_cache[UNIT_CACHE_SIZE];

extern UMap NUMEROBIS_UNITS;
extern UMap NUMEROBIS_UNIT_COMBOS;
extern const char *NUMEROBIS_UNIT_NAMES[];

typedef struct {
  uint16_t id;
  int16_t exp;
} UnitFactor;

typedef struct {
  UnitFactor *data;
  uint16_t len;
  double scalar;
} UnitFactorList;

typedef struct Unit {
  uint64_t hash;
  uint16_t len;
  double scalar;
  UnitFactor data[];
} Unit;

typedef uint64_t ComboKey;

static inline ComboKey u_combo_key(uint64_t a, uint64_t b) {
  if (a < b) {
    uint64_t t = a;
    a = b;
    b = t;
  }
  return (a << 32) | (b & 0xFFFFFFFF);
}

void units_init(void);
void units_shutdown(void);

uint64_t unit_new(uint16_t count, const UnitFactor *factors, double scalar);

Unit *dimensionless_unit(void);

static inline Unit *unit_get(uint64_t hash) {
  uint32_t slot = (uint32_t)(hash & UNIT_CACHE_MASK);
  UnitCacheSlot *cs = &_unit_tls_cache[slot];
  if (__builtin_expect(cs->hash == hash && cs->unit != NULL, 1))
    return (Unit *)cs->unit;

  Unit *u = (Unit *)umap_lookup(&NUMEROBIS_UNITS, hash);
  if (!u)
    u = dimensionless_unit();

  cs->hash = hash;
  cs->unit = u;
  return u;
}

bool is_one(const Unit *u);
uint64_t unit_mul(const Unit *a, const Unit *b, bool invert);
uint64_t unit_pow(const Unit *u, double exp);
UnitFactorList unit_simplify(const UnitFactor *data, uint16_t len,
                             double scalar);
sds unit_print(const Unit *u);

/* ==== MACROS ==== */

#define UF(id, exp) {(id), (exp)}

#define _U_BUILD(scalar, ...)                                                  \
  ({                                                                           \
    const UnitFactor _uf[] = {__VA_ARGS__};                                    \
    unit_new((uint16_t)(sizeof(_uf) / sizeof(_uf[0])), _uf, (double)(scalar)); \
  })

#define U(...) _U_BUILD(1, __VA_ARGS__)
#define U_(scalar, ...) _U_BUILD(scalar, __VA_ARGS__)
#define U_ONE unit_new(0, NULL, 1.0)

extern uint64_t NUMEROBIS_UNIT_ONE_HASH;
#define UNIT_IS_ONE_HASH(h) ((h) == NUMEROBIS_UNIT_ONE_HASH)

#endif
