#include "units.h"
#include "../libs/sds.h"

#include "../libs/bdwgc/include/gc.h"
#include <assert.h>
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

/**
 * Simplifies a list of unit factors by sorting them by ID, merging duplicate
 * dimensions, and culling any factors that cancel out (exponent becomes 0).
 * * @param data Array of UnitFactor structs.
 * @param len Number of elements in the data array.
 * @param scalar The numerical multiplier for the unit.
 * @return A merged UnitFactorList.
 */
UnitFactorList unit_simplify(const UnitFactor *data, uint16_t len,
                             double scalar) {
  // Normalize a zero scalar to 1.0 to prevent breaking the multiplicative
  // chain.
  if (scalar == 0.0)
    scalar = 1.0;

  // dimensionless or empty units return safely.
  if (!data || len == 0)
    return (UnitFactorList){.data = NULL, .len = 0, .scalar = scalar};

  // Duplicate the array so we can safely mutate and sort it.
  UnitFactor *tmp = (UnitFactor *)GC_MALLOC(len * sizeof *tmp);
  memcpy(tmp, data, len * sizeof *tmp);

  // Sort by unit ID.
  qsort(tmp, len, sizeof *tmp, cmp_factor_by_id);

  // First pass: Merge factors with the same ID.
  uint16_t out = 0;
  for (uint16_t i = 0; i < len; i++) {
    if (out > 0 && tmp[out - 1].id == tmp[i].id)
      // Accumulate exponents
      tmp[out - 1].exp += tmp[i].exp;
    else
      // New distinct unit, add it to our active sequence
      tmp[out++] = tmp[i];
  }

  // Second pass: Prune any factors that canceled out entirely (exponent == 0).
  uint16_t final = 0;
  for (uint16_t i = 0; i < out; i++) {
    if (tmp[i].exp != 0)
      tmp[final++] = tmp[i];
  }

  // If everything canceled out, we are left with a scalar.
  if (final == 0) {
    return (UnitFactorList){.data = NULL, .len = 0, .scalar = scalar};
  }

  // Reallocate to trim excess memory footprint before returning.
  tmp = (UnitFactor *)GC_REALLOC(tmp, final * sizeof *tmp);
  return (UnitFactorList){.data = tmp, .len = final, .scalar = scalar};
}

/**
 * Constructs and interns a unit, ensuring that mathematically identical units
 * share the exact same memory address and hash.
 *
 * @param count The number of raw unit factors passed in.
 * @param factors The array of raw UnitFactors.
 * @param scalar The numerical multiplier of an unit.
 * @return The hash representing this unique, interned unit.
 */
uint64_t unit_new(uint16_t count, const UnitFactor *factors, double scalar) {
  assert(NUMEROBIS_UNITS.slots != NULL && "call units_init first");

  // Normalize a zero scalar to 1.0. A scalar of 0 mathematically collapses
  // the unit entirely, but treating it as 1.0 prevents unexpected
  // division-by-zero errors in downstream conversions.
  if (scalar == 0.0)
    scalar = 1.0;

  // Fast path for dimensionless numbers (no factors). If the scalar is
  // also 1.0, we can immediately return the pre-computed global hash for '1'.
  if (!factors || count == 0) {
    if (scalar == 1.0 && NUMEROBIS_UNIT_ONE_HASH)
      return NUMEROBIS_UNIT_ONE_HASH;
  }

  // Normalize the input.
  UnitFactorList sl = unit_simplify(factors, count, scalar);

  GC_reachable_here(sl.data);

  // Did everything cancel out during simplification?
  // If we are left with a scalar of 1.0 and no factors, return the hash for
  // '1'.
  if (sl.len == 0 && sl.scalar == 1.0 && NUMEROBIS_UNIT_ONE_HASH) {
    return NUMEROBIS_UNIT_ONE_HASH;
  }

  // Generate the deterministic hash for this specific combination of
  // factors and scalar.
  uint64_t h = hash_factors(sl.data, sl.len, sl.scalar);

  // Check the global intern pool. If we've seen this exact unit before,
  // just return its existing hash.
  if (umap_contains(&NUMEROBIS_UNITS, h)) {
    return h;
  }

  // Cache miss: We need to allocate a permanent cache place for this new unit.
  size_t sz = sizeof(Unit) + sl.len * sizeof(UnitFactor);
  Unit *u = (Unit *)GC_MALLOC(sz);
  u->hash = h;
  u->len = sl.len;
  u->scalar = sl.scalar;

  // Copy the simplified factors directly into the contiguous tail of the
  // struct.
  if (sl.len > 0)
    memcpy(u->data, sl.data, sl.len * sizeof(UnitFactor));

  GC_reachable_here(sl.data);

  // Add our new unit to the global registry so future calls can find
  // it.
  umap_insert(&NUMEROBIS_UNITS, h, u);
  return h;
}

bool is_one(const Unit *u) { return (u == NULL) || (u->len == 0); }

/**
 * Multiplies (or divides) two units together.
 * * @param a The left-hand unit.
 * @param b The right-hand unit.
 * @param invert If true, division is performed (b's exponents are inverted).
 * @return The hash of the resulting interned unit.
 */
uint64_t unit_mul(const Unit *a, const Unit *b, bool invert) {
  assert(NUMEROBIS_UNITS.slots != NULL && "call units_init first");

  // Fallback to the dimensionless '1' unit if inputs are null.
  if (!a)
    a = (Unit *)umap_lookup(&NUMEROBIS_UNITS, NUMEROBIS_UNIT_ONE_HASH);
  if (!b)
    b = (Unit *)umap_lookup(&NUMEROBIS_UNITS, NUMEROBIS_UNIT_ONE_HASH);

  // Fast-path: Bypass all complex logic.
  if (is_one(a) && a->scalar == 1.0 && is_one(b) && b->scalar == 1.0)
    return NUMEROBIS_UNIT_ONE_HASH;

  // We invert the right-hand hash bits if dividing.
  uint64_t b_key = invert ? ~b->hash : b->hash;
  ComboKey ck = u_combo_key(a->hash, b_key);

  // Fast-path cache lookup: Check our cache first.
  uint32_t cslot = (uint32_t)(ck & UNIT_CACHE_MASK);
  UnitCacheSlot *cc = &_unit_tls_cache[cslot];
  if (__builtin_expect(cc->hash == ck && cc->unit != NULL, 1))
    return ((Unit *)cc->unit)->hash;

  // Secondary cache lookup: Check the global hashmap of previously computed
  // combinations.
  Unit *cached = (Unit *)umap_lookup(&NUMEROBIS_UNIT_COMBOS, ck);
  if (cached) {
    cc->hash = ck;
    cc->unit = cached;
    return cached->hash;
  }

  // Cache miss: We must physically combine the units.
  double result_scalar =
      invert ? (a->scalar / b->scalar) : (a->scalar * b->scalar);

  // Allocate enough space for both sets of factors
  uint16_t merged_len = a->len + b->len;
  UnitFactor *merged =
      merged_len ? (UnitFactor *)GC_MALLOC(merged_len * sizeof *merged) : NULL;

  // Copy left-hand factors.
  if (a->len)
    memcpy(merged, a->data, a->len * sizeof *merged);

  // Append right-hand factors, flipping the exponent sign if we are dividing.
  for (uint16_t i = 0; i < b->len; i++) {
    merged[a->len + i].id = b->data[i].id;
    merged[a->len + i].exp = invert ? (int16_t)-b->data[i].exp : b->data[i].exp;
  }

  // Intern the new unit.
  uint64_t result_hash = unit_new(merged_len, merged, result_scalar);
  Unit *result = unit_get(result_hash);

  // Store the result for future lookups.
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
