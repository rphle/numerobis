#ifndef NUMEROBIS_THROW_H
#define NUMEROBIS_THROW_H

#include "../exceptions/messages.h"
#include "source.h"

typedef struct {
  int line;
  int col;
  int end_line;
  int end_col;
} Location;

#define LOC(line, col, end_line, end_col)                                      \
  &(Location){line, col, end_line, end_col}

typedef struct {
  char *key;
  NumerobisProgram *value;
} ModuleEntry;

extern ModuleEntry *NUMEROBIS_MODULE_REGISTRY;

void u_throw(const int code, const RuntimeMessage *msg, const Location *span);
void rt_err(const char *message, const char *help, const Location *span);

#endif
