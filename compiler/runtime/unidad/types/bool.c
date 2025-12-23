#include <glib.h>
#include <stdbool.h>

bool bool__bool__(bool self) { return self; }
bool int__bool__(int self) { return self != 0; };
bool str__bool__(GString *self) { return self->len > 0; };

bool bool__eq__(bool self, bool other) { return self == other; }
