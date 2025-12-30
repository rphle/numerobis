#include <glib.h>
#include <stdbool.h>

bool int__bool__(gint64 self) { return self != 0; };

bool int__lt__(gint64 self, gint64 other) { return self < other; }
bool int__le__(gint64 self, gint64 other) { return self <= other; }
bool int__gt__(gint64 self, gint64 other) { return self > other; }
bool int__ge__(gint64 self, gint64 other) { return self >= other; }

bool int__eq__(gint64 self, gint64 other) { return self == other; }

bool float__bool__(gdouble self) { return self != 0; };

bool float__lt__(gdouble self, gdouble other) { return self < other; }
bool float__le__(gdouble self, gdouble other) { return self <= other; }
bool float__gt__(gdouble self, gdouble other) { return self > other; }
bool float__ge__(gdouble self, gdouble other) { return self >= other; }

bool float__eq__(gdouble self, gdouble other) { return self == other; }
