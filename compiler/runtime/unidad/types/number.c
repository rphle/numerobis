#include <stdbool.h>

bool int__lt__(int self, int other) { return self < other; }
bool int__le__(int self, int other) { return self <= other; }
bool int__gt__(int self, int other) { return self > other; }
bool int__ge__(int self, int other) { return self >= other; }

bool int__eq__(int self, int other) { return self == other; }

bool float__lt__(float self, float other) { return self < other; }
bool float__le__(float self, float other) { return self <= other; }
bool float__gt__(float self, float other) { return self > other; }
bool float__ge__(float self, float other) { return self >= other; }

bool float__eq__(float self, float other) { return self == other; }
