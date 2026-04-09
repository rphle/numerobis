#include "units.h"
#include "../libs/sds.h"

#include <assert.h>
#include <gc.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

UMap NUMEROBIS_UNITS;
UMap NUMEROBIS_UNIT_COMBOS;

uint64_t NUMEROBIS_UNIT_ONE_HASH = 0;

_Thread_local UnitCacheSlot _unit_tls_cache[UNIT_CACHE_SIZE];

static uint64_t hash_factors(const UnitFactor *data, uint16_t len,
                             double scalar) {
  uint64_t h = 0xcbf29ce484222325ULL;
  for (uint16_t i = 0; i < len; i++) {
    h ^= (uint64_t)data[i].id;
    h *= 0x100000001b3ULL;
    h ^= (uint64_t)(uint16_t)data[i].exp;
    h *= 0x100000001b3ULL;
  }
  uint64_t sbits;
  memcpy(&sbits, &scalar, sizeof sbits);
  h ^= sbits;
  h *= 0x100000001b3ULL;

  return h ? h : 0xdeadbeefcafe0001ULL;
}

static int cmp_factor_by_id(const void *a, const void *b) {
  return (int)((const UnitFactor *)a)->id - (int)((const UnitFactor *)b)->id;
}

Unit *dimensionless_unit(void) {
  uint64_t h = hash_factors(NULL, 0, 1.0);
  Unit *u = (Unit *)umap_lookup(&NUMEROBIS_UNITS, h);
  if (u)
    return u;

  u = (Unit *)GC_MALLOC(sizeof(Unit));
  u->hash = h;
  u->len = 0;
  u->scalar = 1.0;
  umap_insert(&NUMEROBIS_UNITS, h, u);
  return u;
}

void units_init(void) {
  assert(NUMEROBIS_UNITS.slots == NULL && "units_init called twice");

  umap_init(&NUMEROBIS_UNITS, UMAP_INIT_CAP);
  umap_init(&NUMEROBIS_UNIT_COMBOS, UMAP_INIT_CAP);

  Unit *one = dimensionless_unit();
  NUMEROBIS_UNIT_ONE_HASH = one->hash;
}

void units_shutdown(void) {
  if (NUMEROBIS_UNITS.slots) {
    umap_free(&NUMEROBIS_UNITS);
  }
  if (NUMEROBIS_UNIT_COMBOS.slots) {
    umap_free(&NUMEROBIS_UNIT_COMBOS);
  }
}

UnitFactorList unit_simplify(const UnitFactor *data, uint16_t len,
                             double scalar) {
  if (scalar == 0.0)
    scalar = 1.0;

  if (!data || len == 0)
    return (UnitFactorList){.data = NULL, .len = 0, .scalar = scalar};

  UnitFactor *tmp = (UnitFactor *)GC_MALLOC(len * sizeof *tmp);
  memcpy(tmp, data, len * sizeof *tmp);
  qsort(tmp, len, sizeof *tmp, cmp_factor_by_id);

  uint16_t out = 0;
  for (uint16_t i = 0; i < len; i++) {
    if (out > 0 && tmp[out - 1].id == tmp[i].id)
      tmp[out - 1].exp += tmp[i].exp;
    else
      tmp[out++] = tmp[i];
  }

  uint16_t final = 0;
  for (uint16_t i = 0; i < out; i++) {
    if (tmp[i].exp != 0)
      tmp[final++] = tmp[i];
  }

  if (final == 0) {
    return (UnitFactorList){.data = NULL, .len = 0, .scalar = scalar};
  }

  tmp = (UnitFactor *)GC_REALLOC(tmp, final * sizeof *tmp);
  return (UnitFactorList){.data = tmp, .len = final, .scalar = scalar};
}

uint64_t unit_new(uint16_t count, const UnitFactor *factors, double scalar) {
  assert(NUMEROBIS_UNITS.slots != NULL && "call units_init first");

  if (scalar == 0.0)
    scalar = 1.0;

  if (!factors || count == 0) {
    if (scalar == 1.0 && NUMEROBIS_UNIT_ONE_HASH)
      return NUMEROBIS_UNIT_ONE_HASH;
  }

  UnitFactorList sl = unit_simplify(factors, count, scalar);
  GC_reachable_here(sl.data);
  if (sl.len == 0 && sl.scalar == 1.0 && NUMEROBIS_UNIT_ONE_HASH) {
    return NUMEROBIS_UNIT_ONE_HASH;
  }

  uint64_t h = hash_factors(sl.data, sl.len, sl.scalar);

  if (umap_contains(&NUMEROBIS_UNITS, h)) {
    return h;
  }

  size_t sz = sizeof(Unit) + sl.len * sizeof(UnitFactor);
  Unit *u = (Unit *)GC_MALLOC(sz);
  u->hash = h;
  u->len = sl.len;
  u->scalar = sl.scalar;

  if (sl.len > 0)
    memcpy(u->data, sl.data, sl.len * sizeof(UnitFactor));

  GC_reachable_here(sl.data);

  umap_insert(&NUMEROBIS_UNITS, h, u);
  return h;
}

bool is_one(const Unit *u) { return (u == NULL) || (u->len == 0); }

uint64_t unit_mul(const Unit *a, const Unit *b, bool invert) {
  assert(NUMEROBIS_UNITS.slots != NULL && "call units_init first");

  if (!a)
    a = (Unit *)umap_lookup(&NUMEROBIS_UNITS, NUMEROBIS_UNIT_ONE_HASH);
  if (!b)
    b = (Unit *)umap_lookup(&NUMEROBIS_UNITS, NUMEROBIS_UNIT_ONE_HASH);

  if (is_one(a) && a->scalar == 1.0 && is_one(b) && b->scalar == 1.0)
    return NUMEROBIS_UNIT_ONE_HASH;

  uint64_t b_key = invert ? ~b->hash : b->hash;
  ComboKey ck = u_combo_key(a->hash, b_key);

  uint32_t cslot = (uint32_t)(ck & UNIT_CACHE_MASK);
  UnitCacheSlot *cc = &_unit_tls_cache[cslot];
  if (__builtin_expect(cc->hash == ck && cc->unit != NULL, 1))
    return ((Unit *)cc->unit)->hash;

  Unit *cached = (Unit *)umap_lookup(&NUMEROBIS_UNIT_COMBOS, ck);
  if (cached) {
    cc->hash = ck;
    cc->unit = cached;
    return cached->hash;
  }

  double result_scalar =
      invert ? (a->scalar / b->scalar) : (a->scalar * b->scalar);

  uint16_t merged_len = a->len + b->len;
  UnitFactor *merged =
      merged_len ? (UnitFactor *)GC_MALLOC(merged_len * sizeof *merged) : NULL;

  if (a->len)
    memcpy(merged, a->data, a->len * sizeof *merged);
  for (uint16_t i = 0; i < b->len; i++) {
    merged[a->len + i].id = b->data[i].id;
    merged[a->len + i].exp = invert ? (int16_t)-b->data[i].exp : b->data[i].exp;
  }

  uint64_t result_hash = unit_new(merged_len, merged, result_scalar);

  Unit *result = unit_get(result_hash);
  umap_insert(&NUMEROBIS_UNIT_COMBOS, ck, result);
  cc->hash = ck;
  cc->unit = result;

  return result_hash;
}

uint64_t unit_pow(const Unit *u, double exp) {
  assert(NUMEROBIS_UNITS.slots != NULL && "call units_init first");

  if (is_one(u) && u->scalar == 1.0)
    return NUMEROBIS_UNIT_ONE_HASH;

  double new_scalar = pow(u->scalar, exp);

  UnitFactor *factors = (UnitFactor *)GC_MALLOC(u->len * sizeof *factors);
  for (uint16_t i = 0; i < u->len; i++) {
    double raw = (double)u->data[i].exp * exp;
    double rounded = round(raw);
    assert(fabs(raw - rounded) < 1e-9 &&
           "unit_pow: result exponent is not integral");
    assert(rounded >= INT16_MIN && rounded <= INT16_MAX &&
           "unit_pow: result exponent overflows int16_t");
    factors[i].id = u->data[i].id;
    factors[i].exp = (int16_t)rounded;
  }

  uint64_t hash = unit_new(u->len, factors, new_scalar);
  return hash;
}

sds unit_print(const Unit *u) {
  assert(u != NULL);

  if (is_one(u)) {
    if (u->scalar == 1.0)
      return sdsnew("1");
    else
      return sdscatprintf(sdsempty(), "%g", u->scalar);
  }

  sds numer = sdsempty();
  sds denom = sdsempty();

  for (uint16_t i = 0; i < u->len; i++) {
    uint16_t id = u->data[i].id;
    int16_t exp = u->data[i].exp;

    const char *name = NUMEROBIS_UNIT_NAMES[id];
    sds *half = (exp > 0) ? &numer : &denom;
    int16_t abs_exp = (int16_t)(exp > 0 ? exp : -exp);

    if (sdslen(*half) > 0)
      *half = sdscat(*half, "*");

    *half = sdscat(*half, name);
    if (abs_exp != 1)
      *half = sdscatprintf(*half, "^%d", (int)abs_exp);
  }

  sds result = sdsempty();
  if (u->scalar != 1.0)
    result = sdscatprintf(result, "%g*", u->scalar);

  if (sdslen(numer) == 0)
    result = sdscat(result, "1");
  else
    result = sdscatlen(result, numer, sdslen(numer));

  if (sdslen(denom) > 0) {
    result = sdscat(result, "/");
    result = sdscatlen(result, denom, sdslen(denom));
  }

  sdsfree(numer);
  sdsfree(denom);

  return result;
}
