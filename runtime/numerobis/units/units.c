#include "units.h"

#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

GHashTable *NUMEROBIS_UNITS = NULL;
GHashTable *NUMEROBIS_UNIT_COMBOS = NULL;

/* FNV-1a over sorted factors, then fold in the scalar's bit pattern so that
 * 1000*m and 1*m hash differently. */
static uint64_t hash_factors(const UnitFactor *data, uint16_t len,
                             gdouble scalar) {
  uint64_t h = 0xcbf29ce484222325ULL;
  for (uint16_t i = 0; i < len; i++) {
    h ^= (uint64_t)data[i].id;
    h *= 0x100000001b3ULL;
    h ^= (uint64_t)(uint16_t)data[i].exp;
    h *= 0x100000001b3ULL;
  }
  /* Fold scalar in via its IEEE-754 bit pattern. */
  uint64_t sbits;
  memcpy(&sbits, &scalar, sizeof sbits);
  h ^= sbits;
  h *= 0x100000001b3ULL;
  return h;
}

static int cmp_factor_by_id(const void *a, const void *b) {
  const UnitFactor *fa = (const UnitFactor *)a;
  const UnitFactor *fb = (const UnitFactor *)b;
  return (int)fa->id - (int)fb->id;
}

static guint hash_uint64(gconstpointer key) {
  uint64_t v = *(const uint64_t *)key;
  return (guint)(v ^ (v >> 32));
}

static gboolean eq_uint64(gconstpointer a, gconstpointer b) {
  return *(const uint64_t *)a == *(const uint64_t *)b;
}

static uint64_t *dup_uint64(uint64_t v) {
  uint64_t *p = g_malloc(sizeof *p);
  *p = v;
  return p;
}

static Unit *dimensionless_unit(void) {
  uint64_t h = hash_factors(NULL, 0, 1.0);
  Unit *u = g_hash_table_lookup(NUMEROBIS_UNITS, &h);
  if (u)
    return u;

  u = g_malloc(sizeof(Unit));
  u->hash = h;
  u->len = 0;
  u->scalar = 1.0;
  g_hash_table_insert(NUMEROBIS_UNITS, dup_uint64(h), u);
  return u;
}

void units_init(void) {
  assert(NUMEROBIS_UNITS == NULL && "units_init called twice");

  NUMEROBIS_UNITS =
      g_hash_table_new_full(hash_uint64, eq_uint64, g_free, g_free);

  NUMEROBIS_UNIT_COMBOS =
      g_hash_table_new_full(hash_uint64, eq_uint64, g_free, NULL);

  dimensionless_unit();
}

void units_shutdown(void) {
  if (NUMEROBIS_UNIT_COMBOS) {
    g_hash_table_destroy(NUMEROBIS_UNIT_COMBOS);
    NUMEROBIS_UNIT_COMBOS = NULL;
  }
  if (NUMEROBIS_UNITS) {
    g_hash_table_destroy(NUMEROBIS_UNITS);
    NUMEROBIS_UNITS = NULL;
  }
}

UnitFactorList unit_simplify(const UnitFactor *data, uint16_t len,
                             gdouble scalar) {
  if (scalar == 0.0)
    scalar = 1.0;

  if (!data || len == 0)
    return (UnitFactorList){.data = NULL, .len = 0, .scalar = scalar};

  UnitFactor *tmp = g_malloc(len * sizeof *tmp);
  memcpy(tmp, data, len * sizeof *tmp);
  qsort(tmp, len, sizeof *tmp, cmp_factor_by_id);

  uint16_t out = 0;
  for (uint16_t i = 0; i < len; i++) {
    if (out > 0 && tmp[out - 1].id == tmp[i].id) {
      tmp[out - 1].exp += tmp[i].exp;
    } else {
      tmp[out++] = tmp[i];
    }
  }

  uint16_t final = 0;
  for (uint16_t i = 0; i < out; i++) {
    if (tmp[i].exp != 0)
      tmp[final++] = tmp[i];
  }

  if (final == 0) {
    g_free(tmp);
    return (UnitFactorList){.data = NULL, .len = 0, .scalar = scalar};
  }

  tmp = g_realloc(tmp, final * sizeof *tmp);
  return (UnitFactorList){.data = tmp, .len = final, .scalar = scalar};
}

uint64_t unit_new(uint16_t count, const UnitFactor *factors, gdouble scalar) {
  assert(NUMEROBIS_UNITS != NULL && "call units_init first");

  if (scalar == 0.0)
    scalar = 1.0;

  if (!factors || count == 0)
    return dimensionless_unit()->hash;

  UnitFactorList sl = unit_simplify(factors, count, scalar);

  uint64_t h = hash_factors(sl.data, sl.len, sl.scalar);

  if (g_hash_table_contains(NUMEROBIS_UNITS, &h)) {
    g_free(sl.data);
    return h;
  }

  size_t sz = sizeof(Unit) + sl.len * sizeof(UnitFactor);
  Unit *u = g_malloc(sz);
  u->hash = h;
  u->len = sl.len;
  u->scalar = sl.scalar;
  memcpy(u->data, sl.data, sl.len * sizeof(UnitFactor));
  g_free(sl.data);

  g_hash_table_insert(NUMEROBIS_UNITS, dup_uint64(h), u);
  return h;
}

Unit *unit_get(uint64_t hash) {
  assert(NUMEROBIS_UNITS != NULL && "call units_init first");
  Unit *u = g_hash_table_lookup(NUMEROBIS_UNITS, &hash);
  return u ? u : dimensionless_unit();
}

bool is_one(const Unit *u) { return (u == NULL) || (u->len == 0); }

uint64_t unit_mul(const Unit *a, const Unit *b, bool invert) {
  assert(NUMEROBIS_UNITS != NULL && "call units_init first");
  assert(NUMEROBIS_UNIT_COMBOS != NULL && "call units_init first");

  const Unit *dl = dimensionless_unit();
  if (!a)
    a = dl;
  if (!b)
    b = dl;

  uint64_t b_key = invert ? ~b->hash : b->hash;
  ComboKey ck = u_combo_key(a->hash, b_key);

  Unit *cached = g_hash_table_lookup(NUMEROBIS_UNIT_COMBOS, &ck);
  if (cached)
    return cached->hash;

  /* Combine scalars. */
  gdouble result_scalar =
      invert ? (a->scalar / b->scalar) : (a->scalar * b->scalar);

  /* Merge factor lists. */
  uint16_t merged_len = a->len + b->len;
  UnitFactor *merged =
      merged_len ? g_malloc(merged_len * sizeof *merged) : NULL;

  if (a->len)
    memcpy(merged, a->data, a->len * sizeof *merged);
  for (uint16_t i = 0; i < b->len; i++) {
    merged[a->len + i].id = b->data[i].id;
    merged[a->len + i].exp = invert ? (int16_t)-b->data[i].exp : b->data[i].exp;
  }

  uint64_t result_hash = unit_new(merged_len, merged, result_scalar);
  g_free(merged);

  Unit *result = unit_get(result_hash);
  g_hash_table_insert(NUMEROBIS_UNIT_COMBOS, dup_uint64(ck), result);

  return result_hash;
}

uint64_t unit_pow(const Unit *u, gdouble exp) {
  assert(NUMEROBIS_UNITS != NULL && "call u_units_init first");

  if (is_one(u) && u->scalar == 1.0)
    return U_ONE;

  gdouble new_scalar = pow(u->scalar, exp);

  UnitFactor *factors = g_malloc(u->len * sizeof *factors);
  for (uint16_t i = 0; i < u->len; i++) {
    gdouble raw = (gdouble)u->data[i].exp * exp;
    gdouble rounded = round(raw);
    assert(fabs(raw - rounded) < 1e-9 &&
           "unit_pow: result exponent is not integral");
    assert(rounded >= INT16_MIN && rounded <= INT16_MAX &&
           "unit_pow: result exponent overflows int16_t");
    factors[i].id = u->data[i].id;
    factors[i].exp = (int16_t)rounded;
  }

  uint64_t hash = unit_new(u->len, factors, new_scalar);
  g_free(factors);
  return hash;
}

GString *unit_print(const Unit *u) {
  assert(u != NULL);

  GString *result = g_string_new(NULL);

  if (is_one(u)) {
    if (u->scalar == 1.0)
      g_string_assign(result, "1");
    else
      g_string_printf(result, "%g", u->scalar);
    return result;
  }

  GString *numer = g_string_new(NULL);
  GString *denom = g_string_new(NULL);

  for (uint16_t i = 0; i < u->len; i++) {
    uint16_t id = u->data[i].id;
    int16_t exp = u->data[i].exp;

    const char *name = NUMEROBIS_UNIT_NAMES[id];

    GString *half = (exp > 0) ? numer : denom;
    int16_t abs_exp = (int16_t)(exp > 0 ? exp : -exp);

    if (half->len > 0)
      g_string_append_c(half, '*');

    g_string_append(half, name);
    if (abs_exp != 1)
      g_string_append_printf(half, "^%d", (int)abs_exp);
  }

  if (u->scalar != 1.0)
    g_string_printf(result, "%g*", u->scalar);

  if (numer->len == 0)
    g_string_append_c(result, '1');
  else
    g_string_append_len(result, numer->str, (gssize)numer->len);

  if (denom->len > 0) {
    g_string_append_c(result, '/');
    g_string_append_len(result, denom->str, (gssize)denom->len);
  }

  g_string_free(numer, TRUE);
  g_string_free(denom, TRUE);

  return result;
}
