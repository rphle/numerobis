#ifndef NUMEROBIS_UNITS_H
#define NUMEROBIS_UNITS_H

#include <glib.h>
#include <stdbool.h>
#include <stdint.h>

extern GHashTable *NUMEROBIS_UNITS;       /* uint64_t hash -> Unit *  */
extern GHashTable *NUMEROBIS_UNIT_COMBOS; /* ComboKey -> Unit * (borrowed) */
extern const char *NUMEROBIS_UNIT_NAMES[];

typedef struct {
  uint16_t id;
  int16_t exp;
} UnitFactor;

typedef struct {
  UnitFactor *data;
  uint16_t len;
  gdouble scalar;
} UnitFactorList;

typedef struct Unit {
  uint64_t hash;
  uint16_t len;
  gdouble scalar;
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

uint64_t unit_new(uint16_t count, const UnitFactor *factors, gdouble scalar);

Unit *unit_get(uint64_t hash);

bool is_one(const Unit *u);

uint64_t unit_mul(const Unit *a, const Unit *b, bool invert);

uint64_t unit_pow(const Unit *u, gdouble exp);

UnitFactorList unit_simplify(const UnitFactor *data, uint16_t len,
                             gdouble scalar);

GString *unit_print(const Unit *u);

/* ==== MACROS ==== */

#define UF(id, exp) {(id), (exp)}

#define _U_BUILD(scalar, ...)                                                  \
  ({                                                                           \
    const UnitFactor _uf[] = {__VA_ARGS__};                                    \
    unit_new((uint16_t)(sizeof(_uf) / sizeof(_uf[0])), _uf,                    \
             (gdouble)(scalar));                                               \
  })

#define U(...) _U_BUILD(1, __VA_ARGS__)
#define U_(scalar, ...) _U_BUILD(scalar, __VA_ARGS__)
#define U_ONE unit_new(0, NULL, 1.0)

#endif
