#ifndef NUMEROBIS_RUNTIME_H
#define NUMEROBIS_RUNTIME_H

#include <gc.h>

extern int NUMEROBIS__FILE__;
extern const char *NUMEROBIS__FILES__[];
extern char **NUMEROBIS__ARGV__;

void numerobis_runtime_init(void);
void restart_program(void);

#endif
